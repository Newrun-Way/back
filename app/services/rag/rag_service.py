# app/services/rag/rag_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import logging
import threading
import heapq

from app.core.config import get_settings
from app.core.embedder_singleton import GLOBAL_EMBEDDER
from app.services.rag.vector_store import VectorStore
from app.services.rag.chunker import DocumentChunker

logger = logging.getLogger(__name__)


class RAGService:
    """
    - 단일 인덱스 혹은 샤드(Shard) 인덱스 운영
    - 파싱결과(parsed["paragraphs"], parsed["metadata"])를 받아 청킹→임베딩→저장
    - 질의 시 단일/샤드에 맞게 검색하며, 필요 시 ACL 컨텍스트(user_id/depts/projects)를 사용
    """

    def __init__(
        self,
        settings: Optional[object] = None,
        embedder: Optional[GLOBAL_EMBEDDER] = None,
        vector_store: Optional[VectorStore] = None,
        chunker: Optional[DocumentChunker] = None,
    ):
        # ✅ 공통 settings 불러오기 (전역 SSOT)
        self.settings = settings or get_settings()

        # 구성요소
        self.embedder = GLOBAL_EMBEDDER

        self.chunker = chunker or DocumentChunker(
            chunk_size=getattr(self.settings, "CHUNK_SIZE", 800),
            chunk_overlap=getattr(self.settings, "CHUNK_OVERLAP", 150),
        )

        # 공통 설정
        self.vector_dir = Path(getattr(self.settings, "VECTOR_STORE_DIR", "data/vector_store"))
        print(f"RAG서비스 vector_dir: {self.vector_dir}")
        self.index_type = getattr(self.settings, "VECTOR_STORE_INDEX_TYPE", "flat")
        self.sharding_enabled = False

        # 단일 모드용 인덱스
        if not self.sharding_enabled:
            if vector_store is not None:
                print("단일 모드용 VectorStore 주입됨")
                self.vector_store = vector_store
            else:
                print("단일 모드용 VectorStore 생성/로드")
                self.vector_store = self._open_or_create_store(self.vector_dir)

        # 샤드 레지스트리 (필요 시)
        self._lock = threading.Lock()
        self._shards: dict[str, VectorStore] = {}  # shard_key -> store

    # ---------------------------------------------------------------------
    # 내부 유틸: VectorStore open/save
    # ---------------------------------------------------------------------
    def _open_or_create_store(self, dirpath: Path) -> VectorStore:
        """ChromaDB에 맞게 수정된 버전"""
        dirpath.mkdir(parents=True, exist_ok=True)

        try:
            # 1. 로드 시도 (ChromaDB는 load_dir만 필요)
            logger.info(f"VectorStore 로드 시도: {dirpath}")
            return VectorStore.load(load_dir=dirpath)

        except Exception as e:
            # 2. 로드 실패 시 (새로 생성)
            logger.warning(f"VectorStore 로드 실패({e}). 새 ChromaDB 저장소를 생성합니다: {dirpath}")

            # ✅ ChromaDB 생성자 호출 (persist_dir 사용)
            return VectorStore(
                persist_dir=dirpath,
                # 아래 인자들은 호환용 VectorStore에서 경고 로그만 남기고 무시되므로 유지해도 괜찮습니다.
                embedding_dim=self.embedder.embedding_dim,
                index_type=self.index_type
            )

    def _save_store(self, store: VectorStore, dirpath: Path):
        """
        벡터 저장소를 저장합니다.
        (ChromaDB의 경우 store.save()는 경고만 출력하고 무시됩니다)
        """
        dirpath.mkdir(parents=True, exist_ok=True)
        store.save(dirpath)
    # ---------------------------------------------------------------------
    # 샤드 키 규칙/레지스트리
    # ---------------------------------------------------------------------
    @staticmethod
    def _shard_keys_for_index(meta: Dict) -> List[str]:
        return ["global"]

    @staticmethod
    def _shard_keys_for_query(user_id: Optional[str], depts: List[str], projects: List[str]) -> List[str]:
        return ["global"]

    def _open_shard(self, shard_key: str) -> VectorStore:
        sdir = self.vector_dir / "global"
        return self._open_or_create_store(sdir)

    def _save_shard(self, shard_key: str):
        with self._lock:
            store = self._shards.get(shard_key)
            if store is not None:
                self._save_store(store, self.vector_dir / shard_key)

    # ---------------------------------------------------------------------
    # Indexing (단일/샤드)
    # ---------------------------------------------------------------------
    def index_parsed_paragraphs(self, parsed: Dict, *, persist: bool = True) -> Dict:
        meta = parsed.get("metadata", {}) or {}
        docs = []
        for i, text in enumerate(_iter_paragraph_texts(parsed)):
            m = dict(meta); m["paragraph_idx"] = i
            if not text.strip():
                continue
            docs.extend(self.chunker.chunk_text(text, metadata=m))
        if not docs:
            return {"indexed": 0}
        embs = self.embedder.embed_texts([d.page_content for d in docs]).astype(np.float32)
        self.vector_store.add_documents(docs, embs)
        if persist: self._save_store(self.vector_store, self.vector_dir)
        return {"indexed": len(docs)}
    
    def index_parsed_paragraphs_sharded(self, parsed: Dict, *, persist: bool = True) -> Dict:
        #샤딩 제거 -> 글로벌 인덱싱만 수행
        meta = parsed.get("metadata", {}) or {}
        docs = []
        for i, text in enumerate(_iter_paragraph_texts(parsed)):
            m = dict(meta); m["paragraph_idx"] = i
            if not text.strip():
                continue
            docs.extend(self.chunker.chunk_text(text, metadata=m))
        if not docs:
            return {"indexed": 0, "shards": []}

        embs = self.embedder.embed_texts([d.page_content for d in docs]).astype(np.float32)
        global_store = self.vector_store
        global_store.add_documents(docs, embs)

        if persist:
            self._save_store(global_store, self.vector_dir)

        return {"indexed": len(docs), "shards": ["global"]}
    # ---------------------------------------------------------------------
    # Query (단일/샤드)
    # ---------------------------------------------------------------------
    def query(self, question: str, top_k: Optional[int] = None, *, user=None):
        """
        user: {
          "id": 1,
          "dept_id": 3,
          "role": "USER",
          "projects": [1, 5, 7],
          "collab_projects": [3, 9]
        }
        """
        k = top_k or getattr(self.settings, "TOP_K", 5)
        threshold = getattr(self.settings, "SIMILARITY_THRESHOLD", 0.7)

        q_vec = self.embedder.embed_query(question).astype(np.float32)
        results = self.vector_store.search(q_vec, top_k=k * 3, threshold=threshold)

        authorized = []
        for doc, dist in results:
            meta = getattr(doc, "metadata", {}) or {}

            if self._has_access(user, meta):
                authorized.append({
                    "content": doc.page_content,
                    "score": float(dist),
                    "metadata": meta,
                })

            if len(authorized) >= k:
                break

        return authorized

    def _has_access(self, user, meta):
        # SUPER_ADMIN → 모든 문서 접근 가능
        if user["role"] == "SUPER_ADMIN":
            return True

        # 일반 dept 접근
        if meta.get("dept_id") == user["dept_id"]:
            return True

        # 사용자가 속한 프로젝트
        if "project_id" in meta and meta["project_id"] in user.get("projects", []):
            return True

        # 협업 프로젝트
        if "project_id" in meta and meta["project_id"] in user.get("collab_projects", []):
            return True

        return False

    @staticmethod
    def _merge_results(results_by_shard: Dict[str, List[Tuple[object, float]]], top_k: int) -> List[Tuple[str, object, float]]:
        """
        {shard_key: [(doc, dist), ...]} → 거리(dist) 오름차순 상위 top_k 병합
        """
        heap = []  # max-heap (-dist, shard, doc)
        for shard, items in results_by_shard.items():
            for doc, dist in items:
                if len(heap) < top_k:
                    heapq.heappush(heap, (-dist, shard, doc))
                else:
                    if dist < -heap[0][0]:
                        heapq.heapreplace(heap, (-dist, shard, doc))
        out = []
        while heap:
            neg, shard, doc = heapq.heappop(heap)
            out.append((shard, doc, -neg))
        out.reverse()
        return out
    

    # --- 새 유틸: 문단 보정기 -----------------------------------------------
import re

def _iter_paragraph_texts(parsed: dict):
    """
    paragraphs가 비면 text_content / text를 사용해 문단을 생성한다.
    - \n\n(빈 줄) 기준 1차 분해, 그래도 없으면 \n 기준 분해
    - 공백/번호(\n1, \n2 ...)는 그대로 텍스트로 취급 (청킹이 처리)
    """
    # 1) 이미 paragraphs가 있으면 그대로 사용
    paras = parsed.get("paragraphs") or []
    if paras:
        for p in paras:
            t = (p.get("text") or "").strip()
            if t:
                yield t
        return

    # 2) 없으면 text_content / text 에서 생성
    texts = []
    tc = parsed.get("text_content")
    if isinstance(tc, list):
        texts.extend([t for t in tc if isinstance(t, str)])
    elif isinstance(tc, str):
        texts.append(tc)

    raw = "\n".join(texts).strip()
    if not raw:
        return

    # 빈 줄 2개 이상 기준으로 1차 분해 → 그래도 부족하면 단일 개행으로 보조
    blocks = re.split(r"\n{2,}", raw)
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        # 너무 길게 붙은 경우 줄 개행으로 한 번 더 쪼개기(선택)
        if "\n" in b and len(b) > 2_000:
            for seg in re.split(r"\n+", b):
                seg = seg.strip()
                if seg:
                    yield seg
        else:
            yield b
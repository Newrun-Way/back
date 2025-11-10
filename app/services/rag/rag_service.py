# app/services/rag/rag_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import logging
import threading
import heapq

from app.core.config import get_settings
from app.services.rag.embedder import DocumentEmbedder
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
        embedder: Optional[DocumentEmbedder] = None,
        vector_store: Optional[VectorStore] = None,
        chunker: Optional[DocumentChunker] = None,
    ):
        # ✅ 공통 settings 불러오기 (전역 SSOT)
        self.settings = settings or get_settings()

        # 구성요소
        self.embedder = embedder or DocumentEmbedder(
            model_name=getattr(self.settings, "EMBEDDING_MODEL", "BAAI/bge-m3"),
            device=getattr(self.settings, "EMBEDDING_DEVICE", "cpu"),
        )

        self.chunker = chunker or DocumentChunker(
            chunk_size=getattr(self.settings, "CHUNK_SIZE", 800),
            chunk_overlap=getattr(self.settings, "CHUNK_OVERLAP", 150),
        )

        # 공통 설정
        self.vector_dir = Path(getattr(self.settings, "VECTOR_STORE_DIR", "data/vector_store"))
        self.index_type = getattr(self.settings, "VECTOR_STORE_INDEX_TYPE", "flat")
        self.sharding_enabled = bool(getattr(self.settings, "SHARDING_ENABLED", False))

        # 단일 모드용 인덱스
        if not self.sharding_enabled:
            if vector_store is not None:
                self.vector_store = vector_store
            else:
                self.vector_store = self._open_or_create_store(self.vector_dir)

        # 샤드 레지스트리 (필요 시)
        self._lock = threading.Lock()
        self._shards: dict[str, VectorStore] = {}  # shard_key -> store

    # ---------------------------------------------------------------------
    # 내부 유틸: VectorStore open/save
    # ---------------------------------------------------------------------
    def _open_or_create_store(self, dirpath: Path) -> VectorStore:
        dirpath.mkdir(parents=True, exist_ok=True)
        # 존재하면 로드, 없으면 생성
        try:
            # 존재 판단은 VectorStore.load에서 처리하도록 위임해도 됨
            return VectorStore.load(dirpath)
        except Exception:
            logger.info(f"Create VectorStore: type={self.index_type}, dim={self.embedder.embedding_dim}, dir={dirpath}")
            return VectorStore(embedding_dim=self.embedder.embedding_dim, index_type=self.index_type)

    def _save_store(self, store: VectorStore, dirpath: Path):
        dirpath.mkdir(parents=True, exist_ok=True)
        store.save(dirpath)

    # ---------------------------------------------------------------------
    # 샤드 키 규칙/레지스트리
    # ---------------------------------------------------------------------
    @staticmethod
    def _shard_keys_for_index(meta: Dict) -> List[str]:
        keys: List[str] = []
        if meta.get("user_id"): keys.append(f"user={meta['user_id']}")
        for p in meta.get("projects", []) or []: keys.append(f"proj={p}")
        for d in meta.get("depts", []) or []:    keys.append(f"dept={d}")
        if not keys: keys.append("global")
        # 중복 제거(순서 보존)
        seen=set(); out=[]
        for k in keys:
            if k not in seen: seen.add(k); out.append(k)
        return out

    @staticmethod
    def _shard_keys_for_query(user_id: Optional[str], depts: List[str], projects: List[str]) -> List[str]:
        keys: List[str] = []
        if user_id: keys.append(f"user={user_id}")
        for p in projects or []: keys.append(f"proj={p}")
        for d in depts or []:    keys.append(f"dept={d}")
        if not keys: keys.append("global")
        seen=set(); out=[]
        for k in keys:
            if k not in seen: seen.add(k); out.append(k)
        return out

    def _open_shard(self, shard_key: str) -> VectorStore:
        with self._lock:
            if shard_key in self._shards:
                return self._shards[shard_key]
            sdir = self.vector_dir / shard_key
            store = self._open_or_create_store(sdir)
            self._shards[shard_key] = store
            return store

    def _save_shard(self, shard_key: str):
        with self._lock:
            store = self._shards.get(shard_key)
            if store is not None:
                self._save_store(store, self.vector_dir / shard_key)

    # ---------------------------------------------------------------------
    # Indexing (단일/샤드)
    # ---------------------------------------------------------------------
    def index_parsed_paragraphs(self, parsed: Dict, *, persist: bool = True) -> Dict:
        """
        parser 결과(JSON)를 받아 인덱싱
        parsed: {"paragraphs":[{"text":...}, ...], "metadata": {...}}
        - SHARDING_ENABLED=False → 단일 인덱스에 적재
        - True → index_parsed_paragraphs_sharded 사용
        """
        if self.sharding_enabled:
            return self.index_parsed_paragraphs_sharded(parsed, persist=persist)

        paras = parsed.get("paragraphs", [])
        meta = parsed.get("metadata", {}) or {}
        if not paras:
            return {"indexed": 0}

        docs = []
        for i, p in enumerate(paras):
            text = (p.get("text") or "").strip()
            if not text:
                continue
            # 근거 좌표 부여(선택)
            m = dict(meta)
            m["paragraph_idx"] = i
            docs.extend(self.chunker.chunk_text(text, metadata=m))

        if not docs:
            return {"indexed": 0}

        embs = self.embedder.embed_texts([d.page_content for d in docs]).astype(np.float32)
        self.vector_store.add_documents(docs, embs)
        if persist:
            self._save_store(self.vector_store, self.vector_dir)
        return {"indexed": len(docs)}

    def index_parsed_paragraphs_sharded(self, parsed: Dict, *, persist: bool = True) -> Dict:
        """
        샤드 규칙에 따라 여러 인덱스에 중복 인덱싱
        """
        paras = parsed.get("paragraphs", [])
        meta = parsed.get("metadata", {}) or {}
        if not paras:
            return {"indexed": 0, "shards": []}

        docs = []
        for i, p in enumerate(paras):
            text = (p.get("text") or "").strip()
            if not text:
                continue
            m = dict(meta)
            m["paragraph_idx"] = i
            docs.extend(self.chunker.chunk_text(text, metadata=m))

        if not docs:
            return {"indexed": 0, "shards": []}

        embs = self.embedder.embed_texts([d.page_content for d in docs]).astype(np.float32)
        shard_keys = self._shard_keys_for_index(meta)
        total = 0
        for key in shard_keys:
            store = self._open_shard(key)
            store.add_documents(docs, embs)
            total += len(docs)
            if persist:
                self._save_shard(key)
        return {"indexed": total, "shards": shard_keys}

    # ---------------------------------------------------------------------
    # Query (단일/샤드)
    # ---------------------------------------------------------------------
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        *,
        user_id: Optional[str] = None,
        depts: Optional[List[str]] = None,
        projects: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        SHARDING_ENABLED=False → 단일 인덱스에서 검색
        True → query_sharded 사용
        """
        if self.sharding_enabled:
            return self.query_sharded(question, top_k=top_k, user_id=user_id, depts=depts or [], projects=projects or [])

        k = top_k or getattr(self.settings, "TOP_K", 5)
        threshold = getattr(self.settings, "SIMILARITY_THRESHOLD", 0.7)
        q_vec = self.embedder.embed_query(question).astype(np.float32)
        results: List[Tuple[object, float]] = self.vector_store.search(q_vec, top_k=k, threshold=threshold)

        hits: List[Dict] = []
        for doc, dist in results:
            hits.append({
                "content": doc.page_content,
                "score": float(dist),
                "metadata": dict(getattr(doc, "metadata", {})),
            })
        return hits

    def query_sharded(
        self,
        question: str,
        top_k: Optional[int] = None,
        *,
        user_id: Optional[str] = None,
        depts: Optional[List[str]] = None,
        projects: Optional[List[str]] = None,
    ) -> List[Dict]:
        k = top_k or getattr(self.settings, "TOP_K", 5)
        threshold = getattr(self.settings, "SIMILARITY_THRESHOLD", 0.7)
        depts = depts or []
        projects = projects or []

        q = self.embedder.embed_query(question).astype(np.float32)
        shard_keys = self._shard_keys_for_query(user_id=user_id, depts=depts, projects=projects)

        results_by_shard: Dict[str, List[Tuple[object, float]]] = {}
        for key in shard_keys:
            store = self._open_shard(key)
            results_by_shard[key] = store.search(q, top_k=k, threshold=threshold)

        merged = self._merge_results(results_by_shard, top_k=k)

        out: List[Dict] = []
        for shard, doc, dist in merged:
            meta = dict(getattr(doc, "metadata", {}))
            meta["shard"] = shard
            out.append({
                "content": doc.page_content,
                "score": float(dist),
                "metadata": meta,
            })
        return out

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
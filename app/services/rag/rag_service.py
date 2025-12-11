# app/services/rag/rag_service.py
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np
import logging
import threading

from app.core.config import get_settings
from app.core.embedder_singleton import GLOBAL_EMBEDDER
from app.services.rag.vector_store import VectorStore
from app.services.rag.chunker import DocumentChunker
from app.services.rag.reranker import DocumentReranker  # ⬅️ 신규

logger = logging.getLogger(__name__)


def _iter_paragraph_texts(parsed: Dict):
    """
    parsed dict에서 paragraphs → text_content 순으로 텍스트를 꺼내는 헬퍼.
    OWPML1 extract 구조와 호환.
    """
    paragraphs = parsed.get("paragraphs") or []
    if paragraphs:
        for p in paragraphs:
            text = p.get("text") if isinstance(p, dict) else None
            if text:
                yield text
    else:
        texts = parsed.get("text_content") or []
        for t in texts:
            if isinstance(t, str) and t.strip():
                yield t


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
        self.embedder = embedder or GLOBAL_EMBEDDER

        self.chunker = chunker or DocumentChunker(
            chunk_size=getattr(self.settings, "CHUNK_SIZE", 800),
            chunk_overlap=getattr(self.settings, "CHUNK_OVERLAP", 150),
        )

        # 🔹 Reranker 설정
        self.use_reranker: bool = bool(
            getattr(self.settings, "USE_RERANKER", False)
        )
        self.reranker: Optional[DocumentReranker] = None
        if self.use_reranker:
            try:
                reranker_device = getattr(
                    self.settings,
                    "RERANKER_DEVICE",
                    getattr(self.settings, "EMBEDDING_DEVICE", "cpu"),
                )
                self.reranker = DocumentReranker(
                    model_name=getattr(
                        self.settings,
                        "RERANKER_MODEL",
                        "BAAI/bge-reranker-v2-m3",
                    ),
                    device=reranker_device,
                )
                logger.info(
                    "DocumentReranker 활성화: model=%s, device=%s",
                    self.reranker.model_name,
                    reranker_device,
                )
            except Exception as e:
                logger.error(f"Reranker 초기화 실패, 비활성화합니다: {e}")
                self.reranker = None
                self.use_reranker = False

        # 공통 설정
        self.vector_dir = Path(
            getattr(self.settings, "VECTOR_STORE_DIR", "data/vector_store")
        )
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
            logger.warning(
                f"VectorStore 로드 실패({e}). 새 ChromaDB 저장소를 생성합니다: {dirpath}"
            )

            # ✅ ChromaDB 생성자 호출 (persist_dir 사용)
            return VectorStore(
                persist_dir=dirpath,
                # 아래 인자들은 호환용 VectorStore에서 경고 로그만 남기고 무시되므로 유지해도 괜찮습니다.
                embedding_dim=self.embedder.embedding_dim,
                index_type=self.index_type,
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
    def _shard_keys_for_query(
        user_id: Optional[str], depts: List[str], projects: List[str]
    ) -> List[str]:
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
    # Index API
    # ---------------------------------------------------------------------
    def index_parsed_paragraphs(
        self,
        parsed: Dict,
        *,
        persist: bool = True,
    ) -> Dict:
        """
        단일(global) 인덱스에 파싱 결과를 색인
        """
        meta = parsed.get("metadata", {}) or {}
        docs = []
        for i, text in enumerate(_iter_paragraph_texts(parsed)):
            m = dict(meta)
            m["paragraph_idx"] = i
            if not text.strip():
                continue
            docs.extend(self.chunker.chunk_text(text, metadata=m))
        if not docs:
            return {"indexed": 0}
        embs = self.embedder.embed_texts(
            [d.page_content for d in docs]
        ).astype(np.float32)
        self.vector_store.add_documents(docs, embs)
        if persist:
            self._save_store(self.vector_store, self.vector_dir)
        return {"indexed": len(docs)}

    def index_parsed_paragraphs_sharded(
        self,
        parsed: Dict,
        *,
        persist: bool = True,
    ) -> Dict:
        """
        구조 메타(chapter/article/paragraph/hierarchy_path)를 반영하고,
        parser에서 주입한 표(table)도 함께 청킹하여 RAG 인덱싱한다.
        """
        meta = parsed.get("metadata", {}) or {}
        paragraphs = parsed.get("paragraphs", []) or []
        tables = parsed.get("tables", []) or []  # 🔥 parser 리팩토링으로 생성된 표 데이터

        docs: List[Document] = []

        # ============================================================
        # 1) 문단(paragraph) 청킹
        # ============================================================
        for idx, text in enumerate(_iter_paragraph_texts(parsed)):
            if not text or not text.strip():
                continue

            p = paragraphs[idx] if idx < len(paragraphs) else {}

            m = dict(meta)
            m["paragraph_idx"] = idx

            # 🔥 구조 메타 반영
            m["chapter_num"] = p.get("chapter_num")
            m["chapter_title"] = p.get("chapter_title")
            m["article_num"] = p.get("article_num")
            m["article_title"] = p.get("article_title")
            m["paragraph_num"] = p.get("paragraph_num")
            m["hierarchy_path"] = p.get("hierarchy_path")

            # 문단 청킹
            chunks = self.chunker.chunk_text(text, metadata=m)
            docs.extend(chunks)

        # ============================================================
        # 2) 표(table) 청킹 — 🔥 신규 추가
        # ============================================================
        for t in tables:
            table_text = self.chunker._format_table(t)  # 표를 사람이 읽을 수 있는 텍스트로 변환

            m = dict(meta)
            m["type"] = "table"
            m["table_id"] = t.get("table_id")
            m["table_summary"] = t.get("summary", "")

            # 🔥 구조 메타 (parser에서 기본 placeholder, 추후 자동매핑하면 개선됨)
            m["chapter_num"] = t.get("chapter_num")
            m["article_num"] = t.get("article_num")
            m["hierarchy_path"] = t.get("hierarchy_path")

            t_doc = Document(
                page_content=table_text,
                metadata=m,
            )
            docs.append(t_doc)

        # ============================================================
        # 3) 임베딩 + 벡터스토어 저장
        # ============================================================
        if not docs:
            logger.warning("색인할 문서 조각이 없습니다.")
            return {"total_chunks": 0}

        embeddings = self.embedder.embed_documents(docs)

        ids = [
            f"{meta.get('external_doc_id', 'doc')}_{i}"
            for i in range(len(docs))
        ]

        self.vector_store.add_documents(docs, embeddings, ids=ids)

        if persist:
            self._save_store(self.vector_store, self.vector_dir)

        return {
            "total_chunks": len(docs),
            "doc_id": meta.get("external_doc_id"),
        }

    # ---------------------------------------------------------------------
    # Query (Reranker 통합)
    # ---------------------------------------------------------------------
    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        *,
        user=None,
    ):
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
        # 1차: 벡터 검색 (약간 여유 있게 가져오기)
        base_top_k = k * 3
        results: List[Tuple[object, float]] = self.vector_store.search(
            q_vec,
            top_k=base_top_k,
            threshold=threshold,
        )

        # ACL 필터링 (Document, score) 튜플 유지
        acl_filtered: List[Tuple[object, float]] = []
        for doc, dist in results:
            meta = getattr(doc, "metadata", {}) or {}
            if self._has_access(user, meta):
                acl_filtered.append((doc, dist))

        if not acl_filtered:
            return []

        # 🔹 Reranker 적용 여부
        if self.use_reranker and self.reranker is not None:
            rerank_threshold = float(
                getattr(self.settings, "RERANK_THRESHOLD", 0.0)
            )
            rerank_top_k = int(getattr(self.settings, "RERANK_TOP_K", k * 2))
            final_top_k = int(getattr(self.settings, "FINAL_TOP_K", k))

            # 너무 많이는 안 넘기도록 잘라줌
            candidates = acl_filtered[:rerank_top_k]

            reranked = self.reranker.rerank_with_threshold(
                question,
                candidates,
                threshold=rerank_threshold,
                top_k=final_top_k,
            )

            selected = reranked[:k] if reranked else []
        else:
            # Reranker 비활성화 시, 원래 순서대로 상위 k개
            selected = acl_filtered[:k]

        # 응답 포맷 유지
        authorized: List[Dict] = []
        for doc, score in selected:
            meta = getattr(doc, "metadata", {}) or {}
            authorized.append(
                {
                    "content": doc.page_content,
                    # 리랭커가 있으면 score=rerank score, 아니면 L2 거리
                    "score": float(score),
                    "metadata": meta,
                }
            )

        return authorized

    # ---------------------------------------------------------------------
    # ACL
    # ---------------------------------------------------------------------
    def _has_access(self, user, meta):
        # user 정보가 없으면 일단 막는다 (필요 시 정책 변경)
        if not user:
            return False

        # SUPER_ADMIN → 모든 문서 접근 가능
        if user.get("role") == "SUPER_ADMIN":
            return True

        # 일반 dept 접근
        if meta.get("dept_id") == user.get("dept_id"):
            return True

        # 사용자가 속한 프로젝트
        if "project_id" in meta and meta["project_id"] in user.get("projects", []):
            return True

        # 협업 프로젝트
        if "project_id" in meta and meta["project_id"] in user.get(
            "collab_projects", []
        ):
            return True

        return False

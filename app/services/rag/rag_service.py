# app/services/rag/rag_service.py
from typing import List, Dict, Tuple, Optional
import numpy as np
import logging

from app.core.config import get_settings
from app.services.rag.embedder import DocumentEmbedder
from app.services.rag.vector_store import VectorStore
from app.services.rag.chunker import DocumentChunker

logger = logging.getLogger(__name__)


class RAGService:
    """
    RAG 검색 서비스 (Retriever)
    - 문서 → 청크 → 임베딩 → 인덱싱
    - 질의 → 임베딩 → 벡터 검색
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

        # ✅ 구성요소 초기화 (없으면 settings 기반으로 자동 생성)
        self.embedder = embedder or DocumentEmbedder(
            model_name=self.settings.EMBEDDING_MODEL,
            device=getattr(self.settings, "EMBEDDING_DEVICE", "cpu"),
        )

        self.chunker = chunker or DocumentChunker(
            chunk_size=self.settings.CHUNK_SIZE,
            chunk_overlap=self.settings.CHUNK_OVERLAP,
        )

        self.vector_store = vector_store or VectorStore(
            data_dir=self.settings.VECTOR_STORE_DIR,
            embedding_dim=self.embedder.embedding_dim,
        )

    # ------------------------
    # Indexing
    # ------------------------
    def index_texts(self, texts: List[str], base_meta: Dict | None = None) -> Dict:
        """
        문자열 리스트를 받아 청킹 → 임베딩 → 인덱싱
        """
        base_meta = base_meta or {}
        all_docs = []

        for t in texts:
            chunks = self.chunker.chunk_text(t, metadata=base_meta)
            all_docs.extend(chunks)

        if not all_docs:
            return {"indexed": 0}

        logger.info(f"Indexing {len(all_docs)} chunks...")
        embs = self.embedder.embed_texts([d.page_content for d in all_docs]).astype(np.float32)
        self.vector_store.add_documents(all_docs, embs)
        return {"indexed": len(all_docs)}

    def index_parsed_paragraphs(self, parsed: Dict) -> Dict:
        """
        parser 결과(JSON)을 받아 인덱싱
        parsed: {"paragraphs":[{"text":...}, ...], "meta": {...}}
        """
        paras = parsed.get("paragraphs", [])
        meta = parsed.get("meta", {}) or {}

        if not paras:
            return {"indexed": 0}

        docs = []
        for p in paras:
            docs.extend(self.chunker.chunk_text(p["text"], metadata=meta))

        embs = self.embedder.embed_texts([d.page_content for d in docs]).astype(np.float32)
        self.vector_store.add_documents(docs, embs)
        return {"indexed": len(docs)}

    # ------------------------
    # Query
    # ------------------------
    def query(self, question: str, top_k: Optional[int] = None) -> List[Dict]:
        """
        질의 → 임베딩 → VectorStore.search
        """
        k = top_k or self.settings.TOP_K
        q_vec = self.embedder.embed_query(question).astype(np.float32)
        results: List[Tuple[object, float]] = self.vector_store.search(
            q_vec, top_k=k, threshold=self.settings.SIMILARITY_THRESHOLD
        )

        hits: List[Dict] = []
        for doc, dist in results:
            hits.append({
                "content": doc.page_content,
                "score": float(dist),
                "metadata": doc.metadata,
            })
        return hits

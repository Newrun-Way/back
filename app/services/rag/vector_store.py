# app/services/rag/vector_store.py

import chromadb
from chromadb import Client
from chromadb.config import Settings
from pathlib import Path
from loguru import logger
from typing import List, Tuple, Dict, Optional
import numpy as np
from langchain_core.documents import Document
import pickle  # load 호환성을 위해 유지할 수 있으나, ChromaDB는 불필요


class VectorStore:
    """
    ChromaDB 벡터 저장소 클래스
    (기존 FAISS VectorStore와 API 호환성을 유지)
    """

    def __init__(
            self,
            persist_dir: Path,  # ChromaDB는 저장 경로가 필수
            collection_name: str = "global",
            embedding_dim: int = None,  # FAISS 호환용 (사용 X)
            index_type: str = None  # FAISS 호환용 (사용 X)
    ):
        """
        Args:
            persist_dir: DB 저장 디렉토리 (필수)
            collection_name: ChromaDB 컬렉션 이름
            embedding_dim: (무시됨) FAISS 호환용
            index_type: (무시됨) FAISS 호환용
        """
        self.persist_dir = Path(persist_dir) / "global"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        ## FAISS의 init 인자를 받아도 에러가 나지 않도록 처리
        # if embedding_dim is not None:
        #     logger.warning(f"ChromaDB는 'embedding_dim'({embedding_dim}) 인자를 init에서 사용하지 않습니다.")
        # if index_type is not None:
        #     logger.warning(f"ChromaDB는 'index_type'('{index_type}') 인자를 init에서 사용하지 않습니다.")

        self.client = Client(
            Settings(
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_dir),
                anonymized_telemetry=False,
            )
        )

        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # FAISS L2 대신 코사인 유사도 사용
        )

        # ID 생성을 위해 현재 문서 수 추적
        self.doc_count = self.collection.count()
        logger.info(
            f"[ChromaDB] VectorStore 초기화: path={self.persist_dir},"
            f"collection={self.collection_name} (로드된 문서: {self.doc_count}개)")

    def add_documents(
            self,
            documents: List[Document],
            embeddings: np.ndarray
    ):
        """
        문서와 임베딩을 인덱스에 추가 (FAISS API 호환)
        Args:
            documents: Document 리스트
            embeddings: 임베딩 벡터 배열 (shape: [n, dim])
        """
        if len(documents) != len(embeddings):
            raise ValueError("문서 수와 임베딩 수가 일치하지 않습니다")

        if len(documents) == 0:
            logger.warning("추가할 문서가 없습니다.")
            return

        # ChromaDB에 맞는 형식으로 변환
        doc_contents = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]

        # FAISS는 ID를 내부에서 관리했지만, Chroma는 ID가 필수.
        # 중복을 피하기 위해 현재 doc_count 기준으로 ID 생성
        start_id = self.doc_count
        ids = [str(start_id + i) for i in range(len(documents))]

        # 임베딩을 리스트로 변환
        embeddings_list = embeddings.tolist()

        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings_list,
                documents=doc_contents,
                metadatas=metadatas
            )
        except chromadb.errors.IDAlreadyExistsError:
            logger.error("ID 중복 오류 발생. 이미 추가된 데이터일 수 있습니다.")
            return

        new_total = self.collection.count()
        added_count = new_total - self.doc_count
        self.doc_count = new_total

        logger.info(f"문서 추가 완료: {added_count}개 (총 {self.doc_count}개)")

    def search(
            self,
            query_embedding: np.ndarray,
            top_k: int = 5,
            threshold: float = 0.7,
            where_filter: Optional[Dict] = None  # ✅ 'where' 필터 인자 추가
    ) -> List[Tuple[Document, float]]:
        """
        유사 문서 검색 (FAISS API 호환 + ChromaDB 'where' 필터 지원)
        Args:
            query_embedding: 질문 임베딩 벡터
            top_k: 반환할 문서 수
            threshold: 유사도 임계값 (Cosine 거리)
            where_filter: (ChromaDB) 메타데이터 필터 딕셔너리
        """
        if self.collection.count() == 0:
            logger.warning("인덱스가 비어있습니다")
            return []

        if query_embedding.ndim == 1:
            query_list = query_embedding.tolist()
        else:
            query_list = query_embedding[0].tolist()

        # ✅ 'where' 필터를 collection.query에 전달
        res = self.collection.query(
            query_embeddings=[query_list],
            n_results=top_k,
            where=where_filter  # ✅ 전달
        )

        results = []
        if res and res.get("documents"):
            for doc_content, meta, dist in zip(
                    res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                # 코사인 거리 임계값 체크 (0에 가까울수록 유사)
                # threshold (예: 0.7) 보다 *작아야* 유사한 문서임.
                if dist > threshold:
                    continue

                # Document 객체로 복원
                doc = Document(page_content=doc_content, metadata=meta)
                score = float(dist)  # 코사인 거리 (낮을수록 유사)
                results.append((doc, score))

        logger.info(f"검색 완료: {len(results)}개 문서 반환")
        return results

    def save(self, save_dir: Path):
        """
        인덱스 저장 (FAISS API 호환)
        ChromaDB는 PersistentClient 사용 시 자동으로 디스크에 저장됩니다.
        """
        # PersistentClient는 실시간으로 persist_dir에 저장함
        if Path(save_dir) != self.persist_dir:
            logger.warning(f"ChromaDB는 init시 지정된 '{self.persist_dir}'에 자동 저장됩니다.")
            logger.warning(f"'save()' 호출시 지정된 '{save_dir}'는 무시됩니다.")

        logger.info(f"ChromaDB는 '{self.persist_dir}'에 자동 저장됩니다. (별도 save 불필요)")

    @classmethod
    def load(cls, load_dir: Path, collection_name: str = "documents"):
        """
        저장된 ChromaDB 로드 (FAISS API 호환)
        Args:
            load_dir: 로드 디렉토리 (init시 persist_dir와 동일)
            collection_name: 로드할 컬렉션 이름
        Returns:
            VectorStore 인스턴스
        """
        # ChromaDB는 load가 곧 init입니다.
        logger.info(f"ChromaDB 로드 중...: {load_dir}")

        # FAISS.load는 pkl에서 dim, type을 읽었지만 Chroma는 불필요
        store = cls(
            persist_dir=load_dir,
            collection_name=collection_name
        )
        return store

    def get_stats(self) -> Dict:
        """저장소 통계 반환 (FAISS API 호환)"""
        count = self.collection.count()
        # FAISS와 달리 Chroma는 embedding_dim을 명시적으로 저장하지 않음
        return {
            'total_documents': count,
            'embedding_dim': 'N/A (ChromaDB)',
            'index_type': f'ChromaDB ({self.collection_name})',
            'index_size': count  # FAISS의 ntotal과 유사하게 문서 수 반환
        }

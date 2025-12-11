# app/services/rag/vector_store.py

import chromadb
# from chromadb.config import Settings
from pathlib import Path
from loguru import logger
from typing import List, Tuple, Dict, Optional
import numpy as np
from langchain_core.documents import Document


class VectorStore:
    """
    ChromaDB 벡터 저장소 클래스
    (기존 FAISS VectorStore와 API 호환성을 유지)
    """

    def __init__(
            self,
            persist_dir: Path,  # ChromaDB는 저장 경로가 필수
            collection_name: str = "global",
    ):
        """
        Args:
            persist_dir: DB 저장 디렉토리 (필수)
            collection_name: ChromaDB 컬렉션 이름
        """
        # 1. 경로 설정: 입력받은 경로 하위에 "global" 폴더를 사용하도록 설정
        self.persist_dir = Path(persist_dir) / "global"
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        # 2. 클라이언트 초기화
        try:
            self.client = chromadb.PersistentClient(
                path=str(self.persist_dir)
            )
        except Exception as e:
            logger.error(f"ChromaDB Client 초기화 실패: {e}")
            raise e

        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},  # 코사인 유사도 사용
        )

        # ID 생성을 위해 현재 문서 수 추적
        self.doc_count = self.collection.count()
        logger.info(
            f"[ChromaDB] VectorStore 초기화 완료: path={self.persist_dir}, "
            f"collection={self.collection_name} (로드된 문서: {self.doc_count}개)"
        )

    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray,
        ids: Optional[List[str]] = None,
    ):
        """
        문서와 임베딩을 인덱스에 추가 (ids 제공 시 Chroma의 ID를 직접 지정)
        """
        if len(documents) != len(embeddings):
            raise ValueError("문서 수와 임베딩 수가 일치하지 않습니다")

        if len(documents) == 0:
            logger.warning("추가할 문서가 없습니다.")
            return

        # ------------------------------------------------------
        # 🔥 새로운 ID 사용 방식
        # ------------------------------------------------------
        if ids is not None:
            if len(ids) != len(documents):
                raise ValueError("ids 길이가 documents 수와 일치하지 않습니다")
            chroma_ids = ids  # 우리가 정의한 고유 ID 사용
        else:
            # 백워드 호환: 기존 자동 증가 ID 방식
            start_id = self.doc_count
            chroma_ids = [str(start_id + i) for i in range(len(documents))]

        doc_contents = [doc.page_content for doc in documents]
        metadatas = [doc.metadata for doc in documents]
        embeddings_list = embeddings.tolist()

        try:
            self.collection.add(
                ids=chroma_ids,
                embeddings=embeddings_list,
                documents=doc_contents,
                metadatas=metadatas,
            )
        except Exception as e:
            logger.error(f"ChromaDB add 실패: {e}")
            raise e

        new_total = self.collection.count()
        added_count = new_total - self.doc_count
        self.doc_count = new_total

        logger.info(f"문서 추가 완료: {added_count}개 (총 {self.doc_count}개)")

    def search(
            self,
            query_embedding: np.ndarray,
            top_k: int = 5,
            threshold: float = 0.7,
            where_filter: Optional[Dict] = None
    ) -> List[Tuple[Document, float]]:
        """
        유사 문서 검색 (FAISS API 호환 + ChromaDB 'where' 필터 지원)
        """
        if self.collection.count() == 0:
            logger.warning("인덱스가 비어있습니다")
            return []

        if query_embedding.ndim == 1:
            query_list = query_embedding.tolist()
        else:
            query_list = query_embedding[0].tolist()

        # ChromaDB 쿼리 수행
        res = self.collection.query(
            query_embeddings=[query_list],
            n_results=top_k,
            where=where_filter
        )

        results = []
        if res and res.get("documents"):
            # 결과 파싱 (documents, metadatas, distances는 리스트의 리스트 형태)
            documents = res["documents"][0] if res["documents"] else []
            metadatas = res["metadatas"][0] if res["metadatas"] else []
            distances = res["distances"][0] if res["distances"] else []

            for doc_content, meta, dist in zip(documents, metadatas, distances):
                # 코사인 거리 임계값 체크
                if dist > threshold:
                    continue

                doc = Document(page_content=doc_content, metadata=meta)
                score = float(dist)
                results.append((doc, score))

        logger.info(f"검색 완료: {len(results)}개 문서 반환")
        return results

    def save(self, save_dir: Path):
        """
        인덱스 저장 (FAISS API 호환)
        ChromaDB는 PersistentClient 사용 시 자동으로 디스크에 저장됩니다.
        """
        if Path(save_dir) != self.persist_dir:
            logger.warning(f"ChromaDB는 init시 지정된 '{self.persist_dir}'에 자동 저장됩니다.")
        logger.info(f"ChromaDB는 '{self.persist_dir}'에 자동 저장됩니다. (별도 save 불필요)")

    @classmethod
    def load(cls, load_dir: Path, collection_name: str = "global"):
        """
        저장된 ChromaDB 로드 (FAISS API 호환)
        Args:
            load_dir: 로드 디렉토리 (init시 persist_dir와 동일하게 전달됨)
            collection_name: 로드할 컬렉션 이름 (기본값 "global"로 변경)
        """
        logger.info(f"ChromaDB 로드 시도: {load_dir}")

        # cls() 호출 시 __init__이 실행되며, 거기서 /global 경로를 다시 붙이게 됨.
        # 따라서 load_dir는 상위 경로여야 함.
        store = cls(
            persist_dir=load_dir,
            collection_name=collection_name
        )
        return store

    def get_stats(self) -> Dict:
        """저장소 통계 반환"""
        count = self.collection.count()
        return {
            'total_documents': count,
            'embedding_dim': 'N/A (ChromaDB)',
            'index_type': f'ChromaDB ({self.collection_name})',
            'index_size': count
        }
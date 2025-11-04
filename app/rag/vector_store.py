"""
벡터 저장소 모듈
FAISS를 사용한 벡터 인덱싱 및 검색
"""

from typing import List, Tuple, Dict
import numpy as np
import faiss
import pickle
from pathlib import Path
from langchain_core.documents import Document
from loguru import logger


class VectorStore:
    """FAISS 벡터 저장소 클래스"""
    
    def __init__(
        self,
        embedding_dim: int,
        index_type: str = "flat"  # "flat" 또는 "ivf"
    ):
        """
        Args:
            embedding_dim: 임베딩 차원
            index_type: 인덱스 타입 (flat: 정확, ivf: 빠름)
        """
        self.embedding_dim = embedding_dim
        self.index_type = index_type
        
        # FAISS 인덱스 초기화
        if index_type == "flat":
            self.index = faiss.IndexFlatL2(embedding_dim)
        elif index_type == "ivf":
            # IVF 인덱스 (대용량용, 100개 클러스터)
            quantizer = faiss.IndexFlatL2(embedding_dim)
            self.index = faiss.IndexIVFFlat(quantizer, embedding_dim, 100)
        else:
            raise ValueError(f"지원하지 않는 index_type: {index_type}")
        
        # 메타데이터 저장
        self.documents: List[Document] = []
        self.doc_ids: List[int] = []
        
        logger.info(f"VectorStore 초기화: dim={embedding_dim}, type={index_type}")
    
    def add_documents(
        self,
        documents: List[Document],
        embeddings: np.ndarray
    ):
        """
        문서와 임베딩을 인덱스에 추가
        
        Args:
            documents: Document 리스트
            embeddings: 임베딩 벡터 배열 (shape: [n, dim])
        """
        if len(documents) != len(embeddings):
            raise ValueError("문서 수와 임베딩 수가 일치하지 않습니다")
        
        # IVF 인덱스는 학습 필요
        if self.index_type == "ivf" and not self.index.is_trained:
            logger.info("IVF 인덱스 학습 중...")
            self.index.train(embeddings)
        
        # 인덱스에 추가
        start_id = len(self.documents)
        self.index.add(embeddings)
        
        # 메타데이터 저장
        for i, doc in enumerate(documents):
            self.documents.append(doc)
            self.doc_ids.append(start_id + i)
        
        logger.info(f"문서 추가 완료: {len(documents)}개 (총 {len(self.documents)}개)")
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        threshold: float = 0.7
    ) -> List[Tuple[Document, float]]:
        """
        유사 문서 검색
        
        Args:
            query_embedding: 질문 임베딩 벡터
            top_k: 반환할 문서 수
            threshold: 유사도 임계값 (L2 거리 기준)
        
        Returns:
            (Document, score) 튜플 리스트
        """
        if len(self.documents) == 0:
            logger.warning("인덱스가 비어있습니다")
            return []
        
        # 검색 (query_embedding shape: [1, dim])
        if query_embedding.ndim == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        distances, indices = self.index.search(query_embedding, top_k)
        
        # 결과 정리
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # FAISS는 결과 부족 시 -1 반환
                continue
            
            # L2 거리를 유사도 점수로 변환 (낮을수록 유사)
            # 임계값 체크
            if dist > threshold * 10:  # threshold 스케일 조정
                continue
            
            doc = self.documents[idx]
            score = float(dist)
            results.append((doc, score))
        
        logger.info(f"검색 완료: {len(results)}개 문서 반환")
        return results
    
    def save(self, save_dir: Path):
        """
        인덱스와 메타데이터 저장
        
        Args:
            save_dir: 저장 디렉토리
        """
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # FAISS 인덱스 저장
        index_path = save_dir / "faiss_index.bin"
        faiss.write_index(self.index, str(index_path))
        
        # 메타데이터 저장
        metadata_path = save_dir / "metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump({
                'documents': self.documents,
                'doc_ids': self.doc_ids,
                'embedding_dim': self.embedding_dim,
                'index_type': self.index_type
            }, f)
        
        logger.info(f"벡터 저장소 저장 완료: {save_dir}")
    
    @classmethod
    def load(cls, load_dir: Path):
        """
        저장된 인덱스와 메타데이터 로드
        
        Args:
            load_dir: 로드 디렉토리
        
        Returns:
            VectorStore 인스턴스
        """
        load_dir = Path(load_dir)
        
        # 메타데이터 로드
        metadata_path = load_dir / "metadata.pkl"
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)
        
        # VectorStore 생성
        store = cls(
            embedding_dim=metadata['embedding_dim'],
            index_type=metadata['index_type']
        )
        
        # FAISS 인덱스 로드
        index_path = load_dir / "faiss_index.bin"
        store.index = faiss.read_index(str(index_path))
        
        # 메타데이터 복원
        store.documents = metadata['documents']
        store.doc_ids = metadata['doc_ids']
        
        logger.info(f"벡터 저장소 로드 완료: {len(store.documents)}개 문서")
        return store
    
    def get_stats(self) -> Dict:
        """저장소 통계 반환"""
        return {
            'total_documents': len(self.documents),
            'embedding_dim': self.embedding_dim,
            'index_type': self.index_type,
            'index_size': self.index.ntotal
        }


def test_vector_store():
    """벡터 저장소 테스트"""
    from .embedder import DocumentEmbedder
    from langchain_core.documents import Document
    
    # 임베더 초기화
    embedder = DocumentEmbedder()
    
    # 테스트 문서
    docs = [
        Document(page_content="디지털정부 발전에 기여한 공무원을 포상합니다.", 
                 metadata={"doc_id": 1}),
        Document(page_content="포상 대상은 공무원과 민간인입니다.", 
                 metadata={"doc_id": 2}),
        Document(page_content="총 50명 내외를 선발합니다.", 
                 metadata={"doc_id": 3}),
    ]
    
    # 임베딩 생성
    embeddings = embedder.embed_documents(docs)
    
    # 벡터 저장소 생성
    store = VectorStore(embedding_dim=embedder.get_embedding_dim())
    store.add_documents(docs, embeddings)
    
    print(f"\n=== 벡터 저장소 테스트 ===")
    print(f"저장된 문서 수: {len(store.documents)}")
    
    # 검색 테스트
    query = "포상 대상자는 누구인가요?"
    query_embedding = embedder.embed_query(query)
    results = store.search(query_embedding, top_k=2)
    
    print(f"\n질문: {query}")
    print(f"검색 결과:")
    for i, (doc, score) in enumerate(results):
        print(f"\n{i+1}. (score: {score:.4f})")
        print(f"   내용: {doc.page_content}")
        print(f"   메타데이터: {doc.metadata}")
    
    # 저장/로드 테스트
    save_dir = Path("./test_vector_store")
    print(f"\n저장 테스트...")
    store.save(save_dir)
    
    print(f"로드 테스트...")
    loaded_store = VectorStore.load(save_dir)
    print(f"로드된 문서 수: {len(loaded_store.documents)}")
    import shutil
    shutil.rmtree(save_dir)


if __name__ == "__main__":
    test_vector_store()


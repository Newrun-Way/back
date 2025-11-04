"""
임베딩 모듈
BGE-M3 모델을 사용한 텍스트 임베딩
"""

from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from langchain_core.documents import Document
from loguru import logger
import os

class DocumentEmbedder:
    """문서 임베딩 클래스"""
    
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        device: str = None  # "cuda" 또는 "cpu"
    ):
        """
        Args:
            model_name: 임베딩 모델 이름
            device: 실행 디바이스
        """
        self.model_name = model_name
        self.device = device or os.getenv("EMBEDDING_DEVICE", "cpu").lower()
        
        logger.info(f"임베딩 모델 로딩 중: {model_name}")
        try:
            self.model = SentenceTransformer(model_name, device=device)
            logger.info(f"임베딩 모델 로드 완료: {model_name} (device: {device})")
        except Exception as e:
            logger.warning(f"GPU 로딩 실패, CPU로 전환: {e}")
            self.model = SentenceTransformer(model_name, device="cpu")
            self.device = "cpu"
            logger.info(f"임베딩 모델 로드 완료: {model_name} (device: cpu)")
        
        # 모델 정보
        self.embedding_dim = self.model.get_sentence_embedding_dimension()
        logger.info(f"임베딩 차원: {self.embedding_dim}")
    
    def embed_text(self, text: str) -> np.ndarray:
        """
        단일 텍스트 임베딩
        
        Args:
            text: 입력 텍스트
        
        Returns:
            임베딩 벡터 (numpy array)
        """
        if not text or not text.strip():
            logger.warning("빈 텍스트 입력")
            return np.zeros(self.embedding_dim)
        
        embedding = self.model.encode(
            text,
            convert_to_numpy=True,
            show_progress_bar=False
        )
        
        return embedding
    
    def embed_texts(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        여러 텍스트 임베딩 (배치 처리)
        
        Args:
            texts: 텍스트 리스트
            batch_size: 배치 크기
            show_progress: 진행률 표시 여부
        
        Returns:
            임베딩 벡터 배열 (numpy array, shape: [n, dim])
        """
        if not texts:
            logger.warning("빈 텍스트 리스트 입력")
            return np.array([])
        
        logger.info(f"임베딩 생성 중: {len(texts)}개 텍스트")
        
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=show_progress
        )
        
        logger.info(f"임베딩 생성 완료: shape={embeddings.shape}")
        return embeddings
    
    def embed_documents(
        self,
        documents: List[Document],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> np.ndarray:
        """
        Document 객체 리스트 임베딩
        
        Args:
            documents: Document 리스트
            batch_size: 배치 크기
            show_progress: 진행률 표시 여부
        
        Returns:
            임베딩 벡터 배열
        """
        texts = [doc.page_content for doc in documents]
        return self.embed_texts(texts, batch_size, show_progress)
    
    def embed_query(self, query: str) -> np.ndarray:
        """
        검색 쿼리 임베딩 (질문용)
        
        Args:
            query: 검색 질문
        
        Returns:
            임베딩 벡터
        """
        # BGE-M3는 query/passage prefix 불필요 (자동 처리)
        return self.embed_text(query)
    
    def get_embedding_dim(self) -> int:
        """임베딩 차원 반환"""
        return self.embedding_dim


def test_embedder():
    """임베딩 테스트"""
    embedder = DocumentEmbedder()
    
    # 단일 텍스트 테스트
    text = "디지털정부 발전에 기여한 공무원을 포상합니다."
    embedding = embedder.embed_text(text)
    print(f"\n=== 임베딩 테스트 결과 ===")
    print(f"텍스트: {text}")
    print(f"임베딩 shape: {embedding.shape}")
    print(f"임베딩 샘플 (첫 5개): {embedding[:5]}")
    
    # 배치 테스트
    texts = [
        "2024년 포상 계획을 수립합니다.",
        "대상은 공무원과 민간인입니다.",
        "총 50명 내외를 선발합니다."
    ]
    embeddings = embedder.embed_texts(texts, show_progress=False)
    print(f"\n배치 임베딩 shape: {embeddings.shape}")
    
    # 유사도 계산 테스트
    query = "포상 대상자는 누구인가요?"
    query_embedding = embedder.embed_query(query)
    
    # 코사인 유사도
    from numpy.linalg import norm
    similarities = []
    for text, emb in zip(texts, embeddings):
        similarity = np.dot(query_embedding, emb) / (norm(query_embedding) * norm(emb))
        similarities.append(similarity)
        print(f"\n질문: {query}")
        print(f"문서: {text}")
        print(f"유사도: {similarity:.4f}")


if __name__ == "__main__":
    test_embedder()


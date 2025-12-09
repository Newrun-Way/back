# app/services/rag/reranker.py
"""
검색 결과 Reranker 모듈
- OWPML1의 reranker.py를 FastAPI 백엔드 구조에 맞게 통합
"""

from typing import List, Tuple, Optional

import numpy as np
from sentence_transformers import CrossEncoder
from langchain_core.documents import Document
from loguru import logger

from app.core.config import get_settings


class DocumentReranker:
    """BGE Reranker를 사용한 문서 재정렬"""

    def __init__(
        self,
        model_name: Optional[str] = None,
        device: Optional[str] = None,
    ):
        """
        Args:
            model_name: Reranker 모델 이름 (기본값: settings.RERANKER_MODEL)
            device: 실행 장치 ('cuda', 'cpu' 또는 None=자동)
        """
        settings = get_settings()
        self.model_name = model_name or getattr(
            settings,
            "RERANKER_MODEL",
            "BAAI/bge-reranker-v2-m3",
        )

        logger.info(f"Reranker 모델 로딩 중: {self.model_name}")

        try:
            # CrossEncoder 초기화
            if device:
                self.model = CrossEncoder(self.model_name, device=device)
            else:
                # device 미지정 시 sentence-transformers가 자동 선택
                self.model = CrossEncoder(self.model_name)

            logger.info(f"Reranker 로드 완료: {self.model_name}")

        except Exception as e:
            logger.error(f"Reranker 로딩 실패: {e}")
            raise

    def rerank(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        top_k: Optional[int] = None,
    ) -> List[Tuple[Document, float]]:
        """
        질문과 문서 쌍을 재정렬

        Args:
            query: 질문 텍스트
            documents: (Document, score) 튜플 리스트 (score는 원래 벡터 검색 점수)
            top_k: 반환할 상위 문서 수 (None이면 전체)

        Returns:
            재정렬된 (Document, rerank_score) 튜플 리스트
        """
        if not documents:
            logger.warning("재정렬할 문서가 없습니다")
            return []

        # 질문-문서 쌍 생성
        pairs = [[query, doc.page_content] for doc, _ in documents]

        logger.info(f"Reranking 중: {len(pairs)}개 문서")

        # Reranker로 점수 계산
        scores = self.model.predict(pairs)

        # 점수와 문서 매핑
        reranked: List[Tuple[Document, float]] = []
        for i, (doc, _) in enumerate(documents):
            reranked.append((doc, float(scores[i])))

        # 점수 기준 내림차순 정렬 (높을수록 관련성 높음)
        reranked.sort(key=lambda x: x[1], reverse=True)

        # top_k 적용
        if top_k:
            reranked = reranked[:top_k]

        logger.info(f"Reranking 완료: {len(reranked)}개 문서 반환")

        # 점수 범위 로깅
        if reranked:
            scores_range = [score for _, score in reranked]
            logger.info(
                "Rerank 점수 범위: 최고=%.4f, 최저=%.4f",
                max(scores_range),
                min(scores_range),
            )

        return reranked

    def rerank_with_threshold(
        self,
        query: str,
        documents: List[Tuple[Document, float]],
        threshold: Optional[float] = None,
        top_k: Optional[int] = None,
    ) -> List[Tuple[Document, float]]:
        """
        임계값 기반 재정렬

        Args:
            query: 질문 텍스트
            documents: (Document, score) 튜플 리스트
            threshold: 최소 점수 임계값 (기본값: settings.RERANK_THRESHOLD)
            top_k: 반환할 상위 문서 수

        Returns:
            임계값 이상의 재정렬된 문서 리스트
        """
        settings = get_settings()
        if threshold is None:
            threshold = float(getattr(settings, "RERANK_THRESHOLD", 0.0))

        # 재정렬
        reranked = self.rerank(query, documents, top_k=None)

        # 임계값 필터링
        filtered = [(doc, score) for doc, score in reranked if score >= threshold]

        logger.info(
            "임계값 필터링: %s개 → %s개 (threshold=%.4f)",
            len(reranked),
            len(filtered),
            threshold,
        )

        # top_k 적용
        if top_k:
            filtered = filtered[:top_k]

        return filtered

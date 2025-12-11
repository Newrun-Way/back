# app/services/rag/pipeline.py
from app.services.rag.rag_service import RAGService
from app.services.llm.llm_service import LLMGenerator
from app.services.document.table_service import TableService
from app.services.document.table_processor import TableProcessor
from app.core.config import get_settings
import os
from typing import Optional, Dict, Any

class RAGPipeline:
    """RAG 전체 오케스트레이터 (Retriever + Generator)"""
    def __init__(self, settings: Optional[object] = None, **_ignore):
        self.table_service = TableService()
        self.table_processor = TableProcessor()
        self.settings = settings or get_settings()

        # Retriever
        self.retriever = RAGService(settings=self.settings)

        # LLM
        self.llm = LLMGenerator(
            api_key=self.settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
            model=self.settings.LLM_MODEL if hasattr(self.settings, "LLM_MODEL") else "gpt-4o-mini",
            temperature=getattr(self.settings, "LLM_TEMPERATURE", 0.7),
            max_tokens=getattr(self.settings, "LLM_MAX_TOKENS", 1024),
            system_prompt=getattr(self.settings, "SYSTEM_PROMPT", "당신은 문서 기반 QA 어시스턴트입니다."),
            user_prompt_template=getattr(
                self.settings,
                "USER_PROMPT_TEMPLATE",
                "다음 문서를 참고하여 질문에 답하세요.\n\n{context}\n\n질문: {question}\n답변:",
            ),
        )

    # 1 검색 + 답변 생성 (표 포함)
    def query(self, question: str, user: Optional[Dict[str, Any]] = None, top_k: int = 3):
        # 1. 문서 검색 (user 권한 체크 포함)
        contexts = self.retriever.query(question, user=user, top_k=top_k)
        print(f"검색된 컨텍스트 개수: {len(contexts) if contexts else 0}")

        # 2. LLM 답변 (표 자동 포함)
        return self.llm.generate_with_sources(
            contexts,
            question,
            table_service=self.table_service,
            table_processor=self.table_processor,
        )

    # 2 검색만 수행 (ChatService용)
    def retrieve(self, question: str, user: Optional[Dict[str, Any]] = None, top_k: int = 3):
        """
        LLM 생성 없이, 벡터 DB에서 문서만 검색하여 반환합니다.
        ChatService에서 프롬프트를 직접 구성할 때 사용합니다.
        """
        # user 정보를 RAGService.query로 그대로 전달합니다.
        return self.retriever.query(question, user=user, top_k=top_k)
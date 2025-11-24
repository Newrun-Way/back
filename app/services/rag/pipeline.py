# app/services/rag/pipeline.py
from app.services.rag.rag_service import RAGService
from app.services.llm.llm_service import LLMGenerator
from app.core.config import get_settings
import os
from typing import Optional, Dict, Any

class RAGPipeline:
    """RAG 전체 오케스트레이터 (Retriever + Generator)"""

    def __init__(self, settings: Optional[object] = None, **_ignore):
        # ✅ settings를 옵션으로 받고, 없으면 get_settings() 사용
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

    def query(self, question: str, user: Optional[Dict[str, Any]] = None, top_k: int = 3):
        contexts = self.retriever.query(question, user=user, top_k=top_k)
        print(f"검색된 컨텍스트 : {contexts}")
        return self.llm.generate_with_sources(contexts, question)

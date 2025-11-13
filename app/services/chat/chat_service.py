# app/services/chat/chat_service.py

from pathlib import Path
from app.services.rag.pipeline import RAGPipeline
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.chat.prompt_builder import build_prompt
from app.services.llm.llm_service import LLMService
from app.services.rag.embedder import DocumentEmbedder

from app.core.config import get_settings


class ChatService:
    def __init__(self):
        settings = get_settings()

        self.embedder = DocumentEmbedder(
            model=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )

        self.rag = RAGPipeline()   # 기존 back 레포 pipeline 재사용
        self.mem = ChatMemory(
            persist_dir=Path(settings.VECTOR_STORE_DIR) / "chat",
            embedder=self.embedder,
            summary_trigger_turns=6,
        )
        self.llm = LLMService()

    def chat(self, conversation_id: str, message: str):
        # 1) user turn 저장
        self.mem.add_turn(conversation_id, "user", message)

        # 2) context 가져오기
        summary = self.mem.get_summary(conversation_id)
        recent = self.mem.get_recent(conversation_id)

        # 3) 문서 RAG
        rag_result = self.rag.query(message, return_context_only=True)
        docs = [doc["content"] for doc in rag_result]

        # 4) prompt 생성
        prompt = build_prompt(summary, recent, docs, message)

        # 5) LLM 호출
        answer = self.llm.generate(
            system_prompt="기업 문서를 기반으로 답변하는 RAG 챗봇. 현재 질문을 최우선 처리하라.",
            user_prompt=prompt,
        )

        # 6) assistant turn 저장
        self.mem.add_turn(conversation_id, "assistant", answer)

        return answer

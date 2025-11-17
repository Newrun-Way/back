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
            model_name=settings.EMBEDDING_MODEL,
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
        rag_result = self.rag.query(message)
        # --- 디버깅 코드 ---
        print("\n--- RAG 디버그 정보 Start ---")
        print(f"Type of rag_result: {type(rag_result)}")
        print(f"Content of rag_result: {rag_result}")

        # rag_result가 리스트이고, 비어있지 않다면 첫 번째 요소의 타입도 확인합니다.
        if isinstance(rag_result, list) and rag_result:
            print(f"Type of first element (rag_result[0]): {type(rag_result[0])}")
        print("--- RAG 디버그 정보 End ---\n")
        # --- 디버깅 코드 끝 ---
        docs = []  # 기본값 초기화

        # rag_result가 비어있지 않은 리스트인지 확인
        if rag_result and isinstance(rag_result, list):
            # 첫 번째 요소가 딕셔너리(dict)인지 확인
            if isinstance(rag_result[0], dict):
                print("--- RAG Info: Processing list of dicts ---")
                docs = [doc["content"] for doc in rag_result if "content" in doc]
            # 첫 번째 요소가 문자열(str)인지 확인
            elif isinstance(rag_result[0], str):
                print("--- RAG 인포: Processing list of strings ---")
                docs = rag_result
            else:
                # 예상치 못한 타입일 경우 경고 (디버깅용)
                print(f"--- RAG 워닝: 예상치 못한 타입 in rag_result: {type(rag_result[0])} ---")
        else:
            # rag_result가 비어있거나 리스트가 아닐 경우
            print("--- RAG 인포: rag_result는 비어있거나 리스트가 아님. ---")

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

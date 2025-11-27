from pathlib import Path
from typing import Dict, Any, AsyncGenerator
from app.core.db import get_connection
from app.core.config import get_settings
from app.services.rag.pipeline import RAGPipeline
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.chat.prompt_builder import build_prompt
from app.services.llm.llm_service import LLMService
from app.services.rag.embedder import DocumentEmbedder

class ChatService:
    def __init__(self):
        settings = get_settings()
        self.embedder = DocumentEmbedder(
            model_name=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        self.rag = RAGPipeline()

        self.mem = ChatMemory(
            persist_dir=Path(settings.VECTOR_STORE_DIR) / "chat",
            embedder=self.embedder,
            summary_trigger_turns=6,
        )
        self.llm = LLMService()

    # [Helper] DB에서 유저 권한 정보 가져오기
    def _fetch_user_context(self, user_id: int) -> Dict[str, Any]:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = "SELECT id, role, dept_id, project_id FROM users WHERE id = %s"
            cursor.execute(sql, (user_id,))
            row = cursor.fetchone()

            # 검색된 유저가 없거나 에러 시 기본값 (USER 권한)
            if not row:
                return {"id": user_id, "role": "USER", "dept_id": None, "project_id": None}

            if isinstance(row, tuple):
                return {
                    "id": row[0],
                    "role": row[1],
                    "dept_id": row[2],
                    "project_id": row[3]
                }
            return row  # DictCursor라면 그대로 반환
        except Exception as e:
            print(f"[DB Error] 유저 조회 실패: {e}")
            return {"id": user_id, "role": "USER", "dept_id": None, "project_id": None}
        finally:
            cursor.close()
            conn.close()

    def chat(self, conversation_id: str, message: str, user_id: int):

        # 1. 유저 정보(Context)
        user_context = self._fetch_user_context(user_id)

        # 2. 대화 기록 저장
        self.mem.add_turn(conversation_id, "user", message)
        summary = self.mem.get_summary(conversation_id)
        recent = self.mem.get_recent(conversation_id)

        rag_result = self.rag.retriever.query(message, user=user_context)

        # 4. 결과 처리
        docs = []
        if rag_result and isinstance(rag_result, list):
            # 딕셔너리 리스트라면 content만 추출
            if len(rag_result) > 0 and isinstance(rag_result[0], dict):
                docs = [doc["content"] for doc in rag_result if "content" in doc]
            else:
                docs = rag_result

        # 5. 프롬프트 생성
        prompt = build_prompt(summary, recent, docs, message)

        # 6. LLM 답변 생성
        answer = self.llm.generate(
            system_prompt="기업 문서를 기반으로 답변하는 RAG 챗봇. 현재 질문을 최우선 처리하라.",
            user_prompt=prompt,
        )

        # 7. 챗봇 답변 저장
        self.mem.add_turn(conversation_id, "assistant", answer)

        return answer

    async def chat_stream(
            self, conversation_id: str, message: str, user_id: int
    ) -> AsyncGenerator[str, None]:

        # 1. 유저 정보
        user_context = self._fetch_user_context(user_id)

        # 2. 유저 메시지 저장
        self.mem.add_turn(conversation_id, "user", message)

        # 3. 기존 대화 / 요약 가져오기
        summary = self.mem.get_summary(conversation_id)
        recent = self.mem.get_recent(conversation_id)

        # 4. RAG 검색
        rag_result = self.rag.retriever.query(message, user=user_context)

        docs = []
        if isinstance(rag_result, list):
            if rag_result and isinstance(rag_result[0], dict):
                docs = [d["content"] for d in rag_result if "content" in d]

        # 5. 프롬프트 생성
        prompt = build_prompt(summary, recent, docs, message)

        # 6. 스트리밍 LLM 호출
        answer_collector = ""

        async for tok in self.llm.generate_stream(
                system_prompt="기업 문서를 기반으로 답변하는 RAG 챗봇. 현재 질문을 최우선 처리하라.",
                user_prompt=prompt,
        ):
            answer_collector += tok
            yield tok  # SSE로 한 글자씩 전달

        # 7. assistant 메시지 저장
        self.mem.add_turn(conversation_id, "assistant", answer_collector)

        # 8. 스트리밍 끝
        return
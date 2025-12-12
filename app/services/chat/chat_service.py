from pathlib import Path
from typing import Dict, Any, AsyncGenerator

from app.core.db import get_connection
from app.core.config import get_settings
from app.services.rag.pipeline import RAGPipeline
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.chat.prompt_builder import build_prompt
from app.services.llm.llm_service import LLMService
from app.core.embedder_singleton import GLOBAL_EMBEDDER

class ChatService:
    def __init__(self):
        settings = get_settings()
        self.embedder = GLOBAL_EMBEDDER
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

    #비스트리밍채팅
    def chat(self, conversation_id: str, message: str, user_id: int):

        # 1. 유저 정보(Context)
        user_context = self._fetch_user_context(user_id)

        # 2. 대화 기록 저장(user 턴)
        self.mem.add_turn(conversation_id, "user", message)

        # 3. 요약 / 최근 대화
        summary = self.mem.get_summary(conversation_id)
        recent = self.mem.get_recent(conversation_id, k=20)

        # 4. RAG 검색
        rag_result = self.rag.retriever.query(message, user=user_context)

        # 5. 결과 처리
        docs = []
        if rag_result and isinstance(rag_result, list):
            # 딕셔너리 리스트라면 content만 추출
            if len(rag_result) > 0 and isinstance(rag_result[0], dict):
                docs = [doc["content"] for doc in rag_result if "content" in doc]
            else:
                docs = rag_result

        # 6. 프롬프트 생성
        prompt = build_prompt(summary, recent, docs, message)

        # 7. LLM 답변 생성
        answer = self.llm.generate(
            system_prompt="기업 문서를 기반으로 답변하는 RAG 챗봇. 현재 질문을 최우선 처리하라.",
            user_prompt=prompt,
        )

        # 8. 챗봇 답변 저장
        self.mem.add_turn(conversation_id, "assistant", answer)

        return answer

    #스트리밍 채팅
    async def chat_stream(
            self,
            conversation_id: str,
            message: str,
            user_id: int
    ) -> AsyncGenerator[str, None]:
        """
        End-to-End 구조:
        1) 유저컨텍스트 로딩
        2) 메모리에 유저 메시지 저장
        3) 기존 대화요약 + 최근대화 불러오기
        4) RAG 검색
        5) generate_with_sources()로 표 포함 context 생성
        6) prompt_builder로 최종 프롬프트 구성
        7) LLM token 스트리밍
        8) 종료 시 sources/context/answer 송신
        """

        # ---------------------------------------------------------
        # 1) 유저 정보
        # ---------------------------------------------------------
        user_context = self._fetch_user_context(user_id)

        # ---------------------------------------------------------
        # 2) 유저 발화 저장
        # ---------------------------------------------------------
        self.mem.add_turn(conversation_id, "user", message)

        # ---------------------------------------------------------
        # 3) 기존 요약 + 최근 대화
        # ---------------------------------------------------------
        summary = self.mem.get_summary(conversation_id)
        recent_turns = self.mem.get_recent(conversation_id, k=20)

        # ---------------------------------------------------------
        # 4) RAG 검색
        # ---------------------------------------------------------
        rag_contexts = self.rag.query(
            question=message,
            user={"id": user_id}
        )

        # ---------------------------------------------------------
        # 5) generate_with_sources (문단+표 자동 포함)
        # ---------------------------------------------------------
        final = self.llm.generate_with_sources(
            rag_contexts,
            message,
            table_service=self.table_service,
            table_processor=self.table_processor,
        )

        # 문맥 / 출처
        context_str = final["context_used"]
        sources = final["sources"]

        # ---------------------------------------------------------
        # 6) prompt_builder로 최종 프롬프트 구성
        # ---------------------------------------------------------
        # prompt_builder는 summary + 최근대화 + RAG context + user_message를 합친 prompt를 생성해야 한다.
        full_prompt = self.prompt_builder.build(
            summary=summary,
            recent_turns=recent_turns,
            docs=[context_str],  # RAG context
            user_message=message,
            user_context=user_context,
        )

        # 스트리밍 답변을 쌓을 변수
        full_answer = ""

        # ---------------------------------------------------------
        # 7) LLM 스트리밍
        # ---------------------------------------------------------
        async for tok in self.llm.generate_stream(full_prompt):
            full_answer += tok
            yield tok

        # ---------------------------------------------------------
        # 8) 종료 후 메타데이터 전달
        # ---------------------------------------------------------
        # 답변 후 assistant turn 저장
        self.mem.add_turn(conversation_id, "assistant", full_answer)

        # 요약 업데이트
        self.mem.summarize_if_needed(conversation_id)

        final_payload = {
            "answer": full_answer,
            "sources": sources,
            "context_used": context_str,
        }

        yield (
            f"\n\nevent: metadata\n"
            f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
        )

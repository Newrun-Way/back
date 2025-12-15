#app/services/chat/chat_service.py
import json
from pathlib import Path
from typing import Dict, Any, AsyncGenerator

from app.core.db import get_connection
from app.core.config import get_settings
from app.services.rag.pipeline import RAGPipeline
# from app.services.rag.rag_service import RAGService
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.llm.llm_service import LLMService, LLMGenerator
from app.services.document.table_service import TableService
from app.services.document.table_processor import TableProcessor
from app.services.chat.prompt_builder import PromptBuilder
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
        self.llm = LLMGenerator(
            api_key=settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY"),
            model=settings.LLM_MODEL if hasattr(settings, "LLM_MODEL") else "gpt-4o-mini",
            temperature=getattr(settings, "LLM_TEMPERATURE", 0.7),
            max_tokens=getattr(settings, "LLM_MAX_TOKENS", 1024),
            system_prompt=getattr(settings, "SYSTEM_PROMPT", "당신은 문서 기반 QA 어시스턴트입니다."),
            user_prompt_template=getattr(
                settings,
                "USER_PROMPT_TEMPLATE",
                "다음 문서를 참고하여 질문에 답하세요.\n\n{context}\n\n질문: {question}\n답변:",
            ),
        )
        self.prompt_builder = PromptBuilder()
        # 🔥 필수: 표 서비스 등록
        self.table_service = TableService()
        self.table_processor = TableProcessor()

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

    def update_refer_docs(self, chat_session_id: str, final_sources: list[dict]):
        """
        chat_sessions.refer_docs 업데이트
        - 중복 제거
        - 최신 참조 doc_id를 뒤로
        """
        # 1) 이번 응답에서 사용한 doc_ids
        new_doc_ids = [
            s["doc_id"] for s in final_sources
            if s.get("doc_id") not in (None, "", -1)
        ]

        if not new_doc_ids:
            return

        db = get_connection()
        try:
            with db.cursor() as cur:
                # 2) 기존 refer_docs 조회
                cur.execute(
                    "SELECT refer_docs FROM chat_sessions WHERE id=%s",
                    (chat_session_id,)
                )
                row = cur.fetchone()

                old_docs = []
                if row and row.get("refer_docs"):
                    try:
                        old_docs = json.loads(row["refer_docs"])
                    except Exception:
                        old_docs = []

                # 3) 최신순 유지 (old → 제거 → append)
                merged = [d for d in old_docs if d not in new_doc_ids]
                merged.extend(new_doc_ids)

                # 4) 업데이트
                cur.execute(
                    """
                    UPDATE chat_sessions
                    SET refer_docs=%s, updated_at=NOW()
                    WHERE id=%s
                    """,
                    (json.dumps(merged, ensure_ascii=False), chat_session_id),
                )
                db.commit()
        finally:
            db.close()

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
        rag_contexts = self.rag.retrieve(
            question=message,
            user={"id": user_id}
        )
        print("# 4) RAG 검색")
        print("retrieve",rag_contexts)
        print("# 5) generate_with_sources")
        # ---------------------------------------------------------
        # 5) generate_with_sources (문단+표 자동 포함)
        # ---------------------------------------------------------
        final = self.llm.generate_with_sources(
            rag_contexts,
            message,
            table_service=self.table_service,
            table_processor=self.table_processor,
        )
        print("final", final)
        # 문맥 / 출처
        context_str = final["context_used"]
        sources = final["sources"]
        print("# 6) prompt_builder")
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
        print(full_prompt)
        # 스트리밍 답변을 쌓을 변수
        full_answer = ""
        print("# 7) LLM 스트리밍")
        # ---------------------------------------------------------
        # 7) LLM 스트리밍
        # ---------------------------------------------------------
        async for tok in self.llm.generate_stream(full_prompt, message):
            full_answer += tok
            yield tok

        # 8) 종료 후 메타데이터 전달

        final_payload = {
            "answer": full_answer,
            "sources": sources,
            "context_used": context_str,
        }

        self.update_refer_docs(
            chat_session_id=conversation_id,
            final_sources=sources,
        )

        # ✅ 대표 source 1개 선택 (score 기준)
        primary_source = None
        if sources:
            primary_source = max(
                sources,
                key=lambda s: (s.get("score", 0), s.get("paragraph_idx") is not None)
            )

        # ✅ assistant turn 저장 (대표 source만 metadata로)
        self.mem.add_turn(
            conversation_id,
            role="assistant",
            content=full_answer,
            source_meta=primary_source,  # 🔥 신규
        )

        yield (
            f"\n\nevent: metadata\n"
            f"data: {json.dumps(final_payload, ensure_ascii=False)}\n\n"
        )

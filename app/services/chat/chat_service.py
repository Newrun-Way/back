# app/services/chat/chat_service.py
from typing import Dict, Any
from pathlib import Path
from app.services.rag.pipeline import RAGPipeline
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.chat.prompt_builder import build_prompt
from app.services.llm.llm_service import LLMService
from app.services.rag.embedder import DocumentEmbedder

from app.core.config import get_settings
from app.core.db import get_connection


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

        # [추가] DB에서 유저 권한 정보 가져오는 헬퍼 메서드
        def _fetch_user_context(self, user_id: int) -> Dict[str, Any]:
            conn = get_connection()
            cursor = conn.cursor()
            try:
                # users 테이블 컬럼 순서에 맞춰 조회 (id, role, dept_id, project_id)
                sql = "SELECT id, role, dept_id, project_id FROM users WHERE id = %s"
                cursor.execute(sql, (user_id,))
                row = cursor.fetchone()

                if not row:
                    # 유저가 없는 경우 안전한 기본값 리턴 (권한 없음 처리용)
                    return {"id": user_id, "role": "USER", "dept_id": None, "project_id": None}

                return {
                    "id": row[0],
                    "role": row[1],
                    "dept_id": row[2],
                    "project_id": row[3]
                }
            except Exception as e:
                print(f"[DB Error] Fetch User Context Failed: {e}")
                # 에러 시에도 기본값 반환하여 챗봇 멈춤 방지
                return {"id": user_id, "role": "USER", "dept_id": None, "project_id": None}
            finally:
                cursor.close()
                conn.close()

    def chat(self, conversation_id: str, message: str, user_id: int):

        # 1. DB에서 유저 정보(Context) 구성
        user_context = self._fetch_user_context(user_id)

        # 2) user turn 저장
        self.mem.add_turn(conversation_id, "user", message)

        # 3) context 가져오기
        summary = self.mem.get_summary(conversation_id)
        recent = self.mem.get_recent(conversation_id)


        # 4) 문서 RAG
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

        #5. Docs 추출
        docs = []  # 기본값 초기화
        if rag_result and isinstance(rag_result, list):
            # 첫 번째 요소가 딕셔너리(dict)인지 확인
            if isinstance(rag_result[0], dict):
                docs = [doc["content"] for doc in rag_result if "content" in doc]
            # 첫 번째 요소가 문자열(str)인지 확인
            elif isinstance(rag_result[0], str):
                docs = rag_result
            else:
                print(f"--- RAG 워닝: 예상치 못한 타입 in rag_result: {type(rag_result[0])} ---")
        else:
            # rag_result가 비어있거나 리스트가 아닐 경우
            print("--- RAG 인포: rag_result는 비어있거나 리스트가 아님. ---")

        # 6) prompt 생성
        prompt = build_prompt(summary, recent, docs, message)

        # 7) LLM 호출
        answer = self.llm.generate(
            system_prompt="기업 문서를 기반으로 답변하는 RAG 챗봇. 현재 질문을 최우선 처리하라.",
            user_prompt=prompt,
        )

        # 8) assistant turn 저장
        self.mem.add_turn(conversation_id, "assistant", answer)

        return answer

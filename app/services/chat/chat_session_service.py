from app.core.db import get_connection
from app.core.config import get_settings
from app.services.chat.chat_memory_chroma import ChatMemory
from app.core.embedder_singleton import GLOBAL_EMBEDDER
from pathlib import Path
import json

class ChatSessionService:
    def __init__(self):
        settings = get_settings()
        self.embedder = GLOBAL_EMBEDDER
        self.memory = ChatMemory(
            persist_dir=Path(settings.VECTOR_STORE_DIR) / "chat",
            embedder=self.embedder
        )

    def list_sessions(self, user_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                # 1. DB 조회
                cur.execute("""
                    SELECT * FROM chat_sessions 
                    WHERE user_id=%s AND is_deleted=0 
                    ORDER BY updated_at DESC
                """, (user_id,))

                rows = cur.fetchall()  # 이 시점의 rows 안에는 refer_docs가 "[179]" 문자열임

                # 2. 데이터 변환 (String -> List)
                for row in rows:
                    refer_docs = row.get("refer_docs")

                    # 문자열인 경우 JSON 파싱
                    if isinstance(refer_docs, str):
                        try:
                            row["refer_docs"] = json.loads(refer_docs)
                        except Exception:
                            # JSON 형식이 깨져있거나 파싱 실패시 빈 리스트 처리
                            row["refer_docs"] = []

                    # NULL(None)인 경우 빈 리스트로 처리 (Pydantic 호환성)
                    elif refer_docs is None:
                        row["refer_docs"] = []

                    # 이미 list인 경우(드라이버가 변환해준 경우)는 그대로 둠

                return rows
        finally:
            db.close()

    def create_session(self, user_id: int, title: str = None):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_sessions (user_id, title)
                    VALUES (%s, %s)
                """, (user_id, title))
                db.commit()
                return cur.lastrowid
        finally:
            db.close()

    def get_session(self, session_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    SELECT * FROM chat_sessions 
                    WHERE id=%s AND is_deleted=0
                """, (session_id,))
                return cur.fetchone()
        finally:
            db.close()

    def update_session_title(self, session_id: int, title: str):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("""
                    UPDATE chat_sessions 
                    SET title=%s, updated_at=NOW()
                    WHERE id=%s AND is_deleted=0
                """, (title, session_id))
                db.commit()
                # 수정된 행이 있는지 확인 (0이면 해당 세션이 없거나 이미 삭제됨)
                return cur.rowcount > 0
        finally:
            db.close()

    def soft_delete(self, session_id: int):
        db = get_connection()
        try:
            with db.cursor() as cur:
                cur.execute("UPDATE chat_sessions SET is_deleted=1 WHERE id=%s", (session_id,))
                db.commit()
        finally:
            db.close()

    def get_session_with_messages(self, session_id: int):
        session = self.get_session(session_id)
        if not session:
            return None

        refer_docs = session.get("refer_docs")

        if refer_docs:
            if isinstance(refer_docs, str):
                try:
                    # 문자열인 경우 JSON 파싱 시도
                    session["refer_docs"] = json.loads(refer_docs)
                except (json.JSONDecodeError, TypeError):
                    # 파싱 실패 시 빈 리스트
                    session["refer_docs"] = []
            # else: 이미 list나 dict라면 그대로 둠 (DB 드라이버가 자동 변환한 경우)
        else:
            # None이나 빈 값인 경우
            session["refer_docs"] = []

        data = self.memory.chat_col.get(where={"conversation_id": str(session_id)})

        items = list(zip(data["documents"], data["metadatas"]))
        items.sort(key=lambda x: x[1]["created_at"])
        print("=*=items=*=",items)

        messages = [
            {
                "role": meta.get("role"),
                "content": content,
                "created_at": meta.get("created_at"),
                "source_refs": self._parse_source_refs(meta),
            }
            for content, meta in items
        ]


        return {
            "session": session,
            "messages": messages
        }

    def _parse_source_refs(meta):
        raw = meta.get("source_refs")
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except Exception:
                return []
        return raw or []
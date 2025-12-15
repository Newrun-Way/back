from app.core.db import get_connection
from app.core.config import get_settings
from app.services.chat.chat_memory_chroma import ChatMemory
from app.core.embedder_singleton import GLOBAL_EMBEDDER
from pathlib import Path

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
                cur.execute("""
                    SELECT * FROM chat_sessions 
                    WHERE user_id=%s AND is_deleted=0 
                    ORDER BY updated_at DESC
                """, (user_id,))
                return cur.fetchall()
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

        if session and session.get("refer_docs"):
            if isinstance(session["refer_docs"], str):
                try:
                    session["refer_docs"] = json.loads(session["refer_docs"])
                except Exception:
                    session["refer_docs"] = []
        else:
            session["refer_docs"] = []

        data = self.memory.chat_col.get(where={"conversation_id": str(session_id)})

        items = list(zip(data["documents"], data["metadatas"]))
        items.sort(key=lambda x: x[1]["created_at"])

        messages = [
            {
                "role": meta.get("role"),
                "content": content,
                "created_at": meta.get("created_at")
            }
            for content, meta in items
        ]


        return {
            "session": session,
            "messages": messages
        }

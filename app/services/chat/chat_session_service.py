from app.core.db import get_connection

class ChatSessionService:
    def __init__(self):
        self.db = get_connection()

    def list_sessions(self, user_id: int):
        cur = self.db.cursor(dictionary=True)
        cur.execute("SELECT * FROM chat_sessions WHERE user_id=%s AND is_deleted=0 ORDER BY updated_at DESC", (user_id,))
        return cur.fetchall()

    def create_session(self, user_id: int, title: str = None):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO chat_sessions (user_id, title) VALUES (%s, %s)",
            (user_id, title)
        )
        self.db.commit()
        return cur.lastrowid

    def get_session(self, session_id: int):
        cur = self.db.cursor(dictionary=True)
        cur.execute("SELECT * FROM chat_sessions WHERE id=%s AND is_deleted=0", (session_id,))
        return cur.fetchone()

    def soft_delete(self, session_id: int):
        cur = self.db.cursor()
        cur.execute("UPDATE chat_sessions SET is_deleted=1 WHERE id=%s", (session_id,))
        self.db.commit()

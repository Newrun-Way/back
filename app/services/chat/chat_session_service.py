from app.core.db import get_connection
from app.core.config import get_settings
from app.services.chat.chat_memory_chroma import ChatMemory
from app.services.rag.embedder import DocumentEmbedder
from pathlib import Path


class ChatSessionService:
    def __init__(self):
        self.db = get_connection()

        # 🔥 ChromaDB와 동일한 초기화 필요
        settings = get_settings()
        self.embedder = DocumentEmbedder(
            model_name=settings.EMBEDDING_MODEL,
            device=settings.EMBEDDING_DEVICE,
        )
        self.memory = ChatMemory(
            persist_dir=Path(settings.VECTOR_STORE_DIR) / "chat",
            embedder=self.embedder
        )

    # ---------------------------
    # 기존 로직 유지
    # ---------------------------
    def list_sessions(self, user_id: int):
        cur = self.db.cursor()
        cur.execute(
            "SELECT * FROM chat_sessions WHERE user_id=%s AND is_deleted=0 ORDER BY updated_at DESC",
            (user_id,)
        )
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
        cur = self.db.cursor()
        cur.execute(
            "SELECT * FROM chat_sessions WHERE id=%s AND is_deleted=0",
            (session_id,)
        )
        return cur.fetchone()

    def soft_delete(self, session_id: int):
        cur = self.db.cursor()
        cur.execute("UPDATE chat_sessions SET is_deleted=1 WHERE id=%s", (session_id,))
        self.db.commit()

    # ---------------------------
    # 🔥 추가: 세션 + 메시지 반환
    # ---------------------------
    def get_session_with_messages(self, session_id: int):
        session = self.get_session(session_id)
        if not session:
            return None

        # ChromaDB에서 메시지를 조회
        data = self.memory.chat_col.get(where={"conversation_id": str(session_id)})

        items = list(zip(data["documents"], data["metadatas"]))
        items.sort(key=lambda x: x[1]["created_at"])

        messages = []
        for content, meta in items:
            messages.append({
                "role": meta.get("role"),
                "content": content,
                "created_at": meta.get("created_at")
            })

        return {
            "session": session,
            "messages": messages
        }

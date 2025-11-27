import chromadb
from pathlib import Path
from app.core.config import get_settings

settings = get_settings()

class ChatMessageStore:
    """
    단순한 채팅 메시지 저장/조회용 Chroma 래퍼.
    - conversation_id + role 기반으로 메시지를 append-only로 쌓는다.
    - delete_messages() 호출 시에만 해당 세션 전체 메시지를 삭제한다.
    """
    def __init__(self):
        base = Path(settings.VECTOR_STORE_DIR) / "global"
        base.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(base))
        self.history = self._ensure_collection("chat_history")

    def _ensure_collection(self, name: str):
        try:
            return self.client.get_collection(name)
        except:
            return self.client.create_collection(name)

    # 메시지 저장 (user/assistant)
    def add_message(self, session_id: str, role: str, content: str):
        meta = {
            "conversation_id": session_id,
            "role": role,
            "created_at": time.time(),
        }
        self.history.add(
            documents=[content],
            metadatas=[meta],
            ids=[f"{session_id}-{role}-{id(content)}"]
        )

    # 해당 세션의 모든 메시지 조회
    def get_messages(self, session_id: str):
        data = self.history.get(
            where={"conversation_id": session_id},
            include=["documents", "metadatas"]
        )
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []

        items = list(zip(docs, metas))
        # created_at 기준 정렬 (없으면 그대로)
        items.sort(key=lambda x: x[1].get("created_at", 0))

        messages = []
        for text, meta in zip(docs, metas):
            messages.append({
                "role": meta.get("role"),
                "content": text,
                "conversation_id": meta.get("conversation_id"),
                "created_at": meta.get("created_at"),
            })

        return messages

    # 해당 세션 메시지 모두 삭제
    def delete_messages(self, session_id: str):
        data = self.history.get(
            where={"conversation_id": session_id}
        )
        ids = data.get("ids", [])
        if ids:
            self.history.delete(ids)

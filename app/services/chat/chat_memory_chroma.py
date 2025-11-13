# app/services/chat/chat_memory_chroma.py

from datetime import datetime
import chromadb
from chromadb.config import Settings
from pathlib import Path

from loguru import logger


class ChatMemory:
    def __init__(self, persist_dir: Path, embedder, summary_trigger_turns=6):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )

        self.chat_col = self.client.get_or_create_collection(
            name="chat_history",
            metadata={"hnsw:space": "cosine"},
        )

        self.summary_col = self.client.get_or_create_collection(
            name="chat_summary",
            metadata={"hnsw:space": "cosine"},
        )

        self.embedder = embedder
        self.summary_trigger_turns = summary_trigger_turns

    # --------------------------
    # turn add
    # --------------------------
    def add_turn(self, conversation_id: str, role: str, content: str):
        emb = self.embedder.embed_texts([content])[0]

        uid = f"{conversation_id}:{role}:{datetime.utcnow().timestamp()}"

        self.chat_col.add(
            ids=[uid],
            documents=[content],
            metadatas=[{
                "conversation_id": conversation_id,
                "role": role,
                "created_at": datetime.utcnow().isoformat(),
            }],
            embeddings=[emb.tolist()],
        )

        logger.info(f"[ChatMemory] added turn: {uid}")
        self._auto_summarize(conversation_id)

    # --------------------------
    # recent turns
    # --------------------------
    def get_recent(self, conversation_id: str, k=4):
        data = self.chat_col.get(where={"conversation_id": conversation_id})

        items = list(zip(data["documents"], data["metadatas"]))
        items.sort(key=lambda x: x[1]["created_at"])

        return items[-k:]

    # --------------------------
    # summary
    # --------------------------
    def get_summary(self, conversation_id: str) -> str:
        data = self.summary_col.get(where={"conversation_id": conversation_id})
        if not data["documents"]:
            return ""
        return data["documents"][0]

    # --------------------------
    # summarize turn history
    # --------------------------
    def _auto_summarize(self, conversation_id: str):
        data = self.chat_col.get(where={"conversation_id": conversation_id})
        if len(data["documents"]) < self.summary_trigger_turns:
            return

        full_text = "\n".join(data["documents"])

        from app.services.llm.llm_service import LLMService
        llm = LLMService()

        summary = llm.generate(
            system_prompt="다음 대화를 핵심만 남기고 6줄로 요약하라.",
            user_prompt=full_text,
        )

        # 기존 삭제
        self.chat_col.delete(where={"conversation_id": conversation_id})

        emb = self.embedder.embed_texts([summary])[0]

        self.summary_col.add(
            ids=[f"{conversation_id}:summary"],
            documents=[summary],
            metadatas=[{
                "conversation_id": conversation_id,
                "created_at": datetime.utcnow().isoformat(),
            }],
            embeddings=[emb.tolist()],
        )

        logger.info(f"[ChatMemory] summary updated.")

# app/services/chat/chat_memory_chroma.py
from datetime import datetime
import chromadb
from chromadb.config import Settings
from pathlib import Path

from loguru import logger


class ChatMemory:
    """
    - 대화 턴을 ChromaDB에 그대로 쌓는다.
    - 일정 턴 수가 넘으면 요약을 생성하지만, 원본 대화(chat_col)는 삭제하지 않는다.
    - summary_col에는 각 conversation_id 당 최신 요약만 유지한다.
    """
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
    # 턴 추가
    # --------------------------
    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        source_refs: list[dict] | None = None,
    ):

        """
        source_meta 예:
        {
            "doc_id": 179,
            "paragraph_idx": 12,
            "chunk_id": 3
        }
        """
        emb = self.embedder.embed_texts([content])[0]

        uid = f"{conversation_id}:{role}:{datetime.utcnow().timestamp()}"

        metadata = {
            "conversation_id": conversation_id,
            "role": role,
            "created_at": datetime.utcnow().isoformat(),
        }

        # 🔥 대표 근거 1개만 저장
        if source_refs:
            # 그대로 JSON-serializable
            metadata["source_refs"] = source_refs

        self.chat_col.add(
            ids=[uid],
            documents=[content],
            metadatas=[metadata],
            embeddings=[emb.tolist()],
        )

        logger.info(f"[ChatMemory] added turn: {uid}")
        self._auto_summarize(conversation_id)

    # --------------------------
    # 최근 턴
    # --------------------------
    def get_recent(self, conversation_id: str, k=20):
        """
        기본값 k=20 으로 넉넉하게 최근 턴을 돌려준다.
        반환 형태: [(document(str), metadata(dict)), ...]
        """
        data = self.chat_col.get(where={"conversation_id": conversation_id})

        items = list(zip(data["documents"], data["metadatas"]))
        items.sort(key=lambda x: x[1]["created_at"])

        if k is None or k <= 0:
            return items
        return items[-k:]

    # --------------------------
    # 요약
    # --------------------------
    def get_summary(self, conversation_id: str) -> str:
        data = self.summary_col.get(where={"conversation_id": conversation_id})
        if not data["documents"]:
            return ""
        # 한 개만 유지하는 정책
        return data["documents"][0]

    # --------------------------
    # 턴 히스토리 요약
    # --------------------------
    def _auto_summarize(self, conversation_id: str):
        """
        summary_trigger_turns 이상이면 전체 대화를 요약해서
        summary_col 에만 저장. chat_col 원본은 삭제하지 않는다.
        """
        data = self.chat_col.get(where={"conversation_id": conversation_id})
        docs = data.get("documents") or []
        if len(docs) < self.summary_trigger_turns:
            return

        full_text = "\n".join(docs)

        from app.services.llm.llm_service import LLMService
        llm = LLMService()

        summary = llm.generate(
            system_prompt="다음 대화를 핵심만 남기고 6줄로 요약하라.",
            user_prompt=full_text,
        )

        # 이전 요약 삭제
        self.summary_col.delete(where={"conversation_id": conversation_id})

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

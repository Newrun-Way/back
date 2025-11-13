# app/services/rag/vector_store.py

import chromadb
from chromadb.config import Settings
from pathlib import Path
from loguru import logger


class VectorStore:
    def __init__(self, persist_dir: Path, collection_name="documents"):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=Settings(anonymized_telemetry=False)
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def add(self, ids, embeddings, documents, metadatas):
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def search(self, embedding, top_k=5):
        res = self.collection.query(
            query_embeddings=[embedding.tolist()],
            n_results=top_k,
        )

        docs = []
        if res and res.get("documents"):
            for doc, meta, dist in zip(
                res["documents"][0], res["metadatas"][0], res["distances"][0]
            ):
                docs.append({"content": doc, "metadata": meta, "score": dist})
        return docs

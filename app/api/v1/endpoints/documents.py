# app/api/v1/endpoints/documents.py

from fastapi import APIRouter
from pathlib import Path
from app.core.config import get_settings
import chromadb
import json

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()

@router.get("/")
def list_documents():
    base = Path(settings.UPLOAD_DIR)
    docs = []

    # 1-dept → user_id
    for user_dir in base.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name

        # 2-depth → doc_id
        for doc_dir in user_dir.iterdir():
            if not doc_dir.is_dir():
                continue

            doc_id = doc_dir.name

            # 파일 찾기
            files = [f.name for f in doc_dir.iterdir() if f.is_file()]

            docs.append({
                "user_id": user_id,
                "doc_id": doc_id,
                "files": files,
                "path": str(doc_dir)
            })

    return docs

@router.get("/{user_id}/{doc_id}/content")
def get_document_content(user_id: str, doc_id: str):
    # 1) 해당 user의 shard 경로
    shard_dir = f"app/data/vector_store/{user_id}"

    # 2) Chroma 연결
    client = chromadb.PersistentClient(path=shard_dir)
    col = client.get_collection("documents")  # 실제 컬렉션명 맞춰야 함

    # 3) doc_id로 chunk 전부 가져오기
    result = col.get(where={"doc_id": doc_id})

    docs = result["documents"]
    metas = result["metadatas"]

    # 4) chunk_index 기준으로 정렬 후 하나의 문서로 합치기
    items = list(zip(docs, metas))
    items.sort(key=lambda x: x[1].get("chunk_index", 0))

    merged_text = "\n".join([doc for doc, _ in items])

    return {
        "user_id": user_id,
        "doc_id": doc_id,
        "chunk_count": len(items),
        "content": merged_text,
        "chunks": [
            {
                "index": meta.get("chunk_index"),
                "content": doc
            }
            for doc, meta in items
        ]
    }
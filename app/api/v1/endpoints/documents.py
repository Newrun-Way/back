# app/api/v1/endpoints/documents.py

from fastapi import APIRouter,HTTPException
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

@router.get("/{user_id}/{doc_id}")
def get_document_detail(user_id: str, doc_id: str):
    # 1) 샤드 디렉토리 위치
    shard_path = Path(settings.VECTOR_STORE_DIR) / user_id
    if not shard_path.exists():
        raise HTTPException(404, f"Shard {user_id} not found")

    # 2) 크로마 클라이언트 로드
    client = chromadb.PersistentClient(path=str(shard_path))

    # 3) documents 컬렉션 로드
    try:
        col = client.get_collection("documents")
    except:
        raise HTTPException(404, "documents collection not found")

    # 4) 실제 필터 조건: user_id + external_doc_id 매칭
    result = col.get(
        where={
            "user_id": int(user_id) if user_id.isdigit() else user_id,
            "external_doc_id": doc_id
        },
        include=["documents", "metadatas"]
    )

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    if len(docs) == 0:
        return {
            "user_id": user_id,
            "doc_id": doc_id,
            "chunks": [],
            "total_chunks": 0
        }

    # 5) chunk 순서 정렬
    items = list(zip(docs, metas))
    items.sort(key=lambda x: x[1].get("paragraph_idx", 0))

    # 6) 문서 merge
    merged = "\n".join([t[0] for t in items])

    return {
        "user_id": user_id,
        "doc_id": doc_id,
        "total_chunks": len(items),
        "content": merged,
        "chunks": [
            {
                "paragraph_idx": meta.get("paragraph_idx"),
                "content": text,
                "metadata": meta
            }
            for text, meta in items
        ]
    }
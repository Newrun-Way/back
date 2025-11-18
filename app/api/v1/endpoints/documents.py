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

@router.get("/{user_id}/{doc_id}", summary="문서 상세조회 (문단 전체)", tags=["documents"])
async def get_document_detail(user_id: str, doc_id: str):
    vector = RAGVectorStore()  # settings 기반으로 자동 샤드 로드

    collection = vector.get_collection("documents")
    if collection is None:
        raise HTTPException(404, "documents collection not found")

    # doc_id는 metadata.external_doc_id에 저장해둠
    results = collection.get(
        where={
            "user_id": int(user_id),
            "external_doc_id": doc_id
        },
        include=["documents", "embeddings", "metadatas"]
    )

    if not results or len(results.get("documents", [])) == 0:
        return {
            "user_id": user_id,
            "doc_id": doc_id,
            "total_chunks": 0,
            "chunks": []
        }

    chunks = []
    docs = results["documents"]
    metas = results["metadatas"]

    for i in range(len(docs)):
        chunks.append({
            "chunk_id": metas[i].get("paragraph_idx", i),
            "content": docs[i],
            "metadata": metas[i]
        })

    # paragraph_idx 기준 정렬
    chunks.sort(key=lambda x: x["chunk_id"])

    return {
        "user_id": user_id,
        "doc_id": doc_id,
        "total_chunks": len(chunks),
        "chunks": chunks
    }

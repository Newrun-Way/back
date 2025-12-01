# app/api/v1/endpoints/rag_admin.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import chromadb
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService

router = APIRouter(prefix="/rag-admin", tags=["dev"])
settings = get_settings()

@router.get("/dump")
def dump_all_chroma(limit: int = 5000):
    """
    ChromaDB 안의 전체 문서를 덤프해서 디버깅하는 API.
    external_doc_id mismatch 여부 확인 가능.
    """
    try:
        rag = RAGService()
        col = rag.vector_store.collection
    except Exception as e:
        raise HTTPException(500, f"Chroma 로드 실패: {e}")

    try:
        result = col.get(include=["documents", "metadatas"], limit=limit)
    except Exception as e:
        raise HTTPException(500, f"VectorStore get() 실패: {e}")

    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    dump = []

    for i in range(len(ids)):
        meta = metadatas[i] or {}
        doc_preview = ""

        if documents[i]:
            # 문서 첫 80자만 출력
            doc_preview = documents[i][:80].replace("\n", " ")

        dump.append({
            "idx": i,
            "id": ids[i],
            "external_doc_id": meta.get("external_doc_id"),
            "paragraph_idx": meta.get("paragraph_idx"),
            "project_id": meta.get("project_id"),
            "user_id": meta.get("user_id"),
            "category": meta.get("category"),
            "preview": doc_preview
        })

    return {
        "count": len(dump),
        "items": dump
    }
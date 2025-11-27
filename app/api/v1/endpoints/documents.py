# app/api/v1/endpoints/documents.py

from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService
from app.services.document.document_service import DocumentService

import json

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()
doc_service = DocumentService()

GLOBAL_DIR_NAME = "global"
svc = DocumentService()

@router.get("/")
def list_documents(dept_id: int | None = None, project_id: int | None = None):
    return svc.list(dept_id, project_id)


@router.get("/{doc_pk}")
def get_document_detail(doc_pk: int):
    """
    문서 상세 조회 (documents.id 기반)
    """

    # 1) DB에서 문서 조회
    doc = doc_service.get_by_id(doc_pk)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    external_doc_id = doc["external_doc_id"]

    # 2) RAG 서비스 접근
    try:
        rag = RAGService()
        col = rag.vector_store.collection
    except Exception as e:
        raise HTTPException(500, f"RAGService 초기화 실패: {e}")

    # 3) 벡터 DB에서 external_doc_id로 chunk 조회
    result = col.get(
        where={"external_doc_id": external_doc_id},
        include=["documents", "metadatas"]
    )

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    if len(docs) == 0:
        return {
            "id": doc_pk,
            "external_doc_id": external_doc_id,
            "chunks": [],
            "total_chunks": 0,
            "message": "해당 문서는 아직 파싱/임베딩되지 않았습니다."
        }

    # 4) 정렬
    items = list(zip(docs, metas))
    items.sort(key=lambda x: x[1].get("paragraph_idx", 0))

    merged_text = "\n".join([text for text, _ in items])

    # 5) 응답
    return {
        "id": doc_pk,
        "external_doc_id": external_doc_id,
        "original_filename": doc["original_filename"],
        "total_chunks": len(items),
        "content": merged_text,
        "chunks": [
            {
                "paragraph_idx": meta.get("paragraph_idx"),
                "content": text,
                "metadata": meta
            }
            for text, meta in items
        ]
    }


@router.get("/download/{doc_id}", summary="문서 다운로드 by PK id")
def download_document(doc_id: int):
    # 1) DB 조회 (PK 기준)
    doc = doc_service.get_by_id(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    stored_path = doc["stored_path"]  # 예: global/감사규정_20240101_123000/original.hwp
    file_path = Path(settings.UPLOAD_DIR) / stored_path

    if not file_path.exists():
        raise HTTPException(404, f"파일을 찾을 수 없습니다: {file_path}")

    # 다운로드 파일명
    download_name = doc["original_filename"]

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/octet-stream"
    )
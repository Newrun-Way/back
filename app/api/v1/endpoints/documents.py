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

GLOBAL_DIR_NAME = "global"
svc = DocumentService()

@router.get("/")
def list_documents(dept_id: int | None = None, project_id: int | None = None):
    return svc.list(dept_id, project_id)


@router.get("/{doc_id}")
def get_document_detail(doc_id: str):
    """
    문서 상세 조회 (벡터 DB)
    """

    # 1) RAG 서비스 인스턴스 생성 (또는 호출)
    try:
        rag = RAGService()
        # [중요] RAGService가 들고 있는 collection 객체를 가져옵니다.
        # 구조에 따라 rag.vector_store.collection 또는 rag.collection 일 수 있습니다.
        # 보통 VectorStore 클래스 안에 collection이 있습니다.
        col = rag.vector_store.collection

    except Exception as e:
        raise HTTPException(500, f"RAG Service/VectorStore access failed: {e}")

    #2 (global DB에 user_id 메타데이터가 남아있더라도, 입력값이 없으므로 doc_id로만 찾습니다)
    result = col.get(
        where={"external_doc_id": doc_id},
        include=["documents", "metadatas"]
    )

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    if len(docs) == 0:
        return {
            "doc_id": doc_id,
            "chunks": [],
            "total_chunks": 0,
            "message": "Document not found in 벡터 DB"
        }

    # 3) chunk 순서 정렬
    items = list(zip(docs, metas))
    items.sort(key=lambda x: x[1].get("paragraph_idx", 0))

    # 4) 문서 merge
    merged = "\n".join([t[0] for t in items])

    return {
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

@router.get("/download/{doc_id}", summary="문서 다운로드")
def download_document(doc_id: str):
    """
    문서 다운로드 (파일 시스템)
    - user_id 없이 doc_id로만 조회
    - 경로: settings.UPLOAD_DIR / global / {doc_id}
    """

    base = Path(settings.UPLOAD_DIR)

    # 1) 파일 경로: 무조건 'global' 폴더 안의 doc_id 폴더를 찾습니다.
    # 예: /data/upload/global/감사규정(2024년도 12월 개정).hwp/
    doc_dir = base / GLOBAL_DIR_NAME / doc_id

    if not doc_dir.exists() or not doc_dir.is_dir():
        raise HTTPException(404, f"Document folder not found: {doc_dir}")

    # 2) 원본 파일 찾기 (original.*)
    files = list(doc_dir.glob("original.*"))
    if not files:
        raise HTTPException(404, f"No original file found in folder: {doc_dir}")

    file_path = files[0]
    file_ext = file_path.suffix

    # 3) 다운로드 파일명 결정 로직
    if doc_id.lower().endswith(file_ext.lower()):
        download_name = doc_id
    else:
        download_name = f"{doc_id}{file_ext}"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/octet-stream"
    )
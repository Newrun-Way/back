# app/api/v1/endpoints/async_doc.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import shutil
import uuid
from celery.result import AsyncResult

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.tasks.rag_tasks import process_document
from app.services.document.document_service import DocumentService
from app.services.rag.pipeline import RAGPipeline
from pydantic import BaseModel

router = APIRouter(prefix="/async", tags=["Async Document Pipeline"])

settings = get_settings()
doc_service = DocumentService()

# --------------------------
# 1) 업로드 + 비동기 처리
# --------------------------
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    dept_id: int = Form(...),
    project_id: int = Form(...),
    category: str = Form(...)
):
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    doc_id = f"doc_{uuid.uuid4().hex}"
    saved_path = uploads_dir / f"{doc_id}_{file.filename}"

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # ---- DB 스키마에 맞춘 메타데이터 저장 ----
    metadata = doc_service.create(
        doc_id=doc_id,
        orginal_filename=file.filename,
        user_id=user_id,
        dept_id=dept_id,
        project_id=project_id,
        category=category,
        file_type=Path(file.filename).suffix.lstrip("."),
        total_size=saved_path.stat().st_size
    )

    # ---- Celery Task 등록 ----
    task = process_document.apply_async(
        args=[str(saved_path), metadata]
    )

    return {
        "task_id": task.id,
        "doc_id": doc_id,
        "message": "문서 처리 시작"
    }


# --------------------------
# 2) 상태 조회
# --------------------------
@router.get("/status/{task_id}")
def get_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.state,
        "info": result.info
    }


# --------------------------
# 3) RAG 질의응답
# --------------------------
class QueryRequest(BaseModel):
    query: str
    top_k: int | None = 5

@router.post("/query")
def rag_query(req: QueryRequest):
    try:
        pipeline = RAGPipeline()
        result = pipeline.query(req.query, top_k=req.top_k or 5)
        return result
    except Exception as e:
        raise HTTPException(500, f"RAG query failed: {e}")

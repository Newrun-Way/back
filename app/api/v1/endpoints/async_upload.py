# app/api/v1/endpoints/async_upload.py
from fastapi import APIRouter, UploadFile, File, Form
from pathlib import Path
import shutil
import uuid
from app.tasks.rag_tasks import process_document
from app.core.config import get_settings
from app.services.document.document_service import DocumentService

router = APIRouter(prefix="/async", tags=["Async Document"])

settings = get_settings()
doc_service = DocumentService()


@router.post("/upload")
async def upload_document(
        file: UploadFile = File(...),
        user_id: int = Form(...),
        dept_id: int = Form(...),
        project_id: int = Form(...),
        category: str = Form(...)
):
    """비동기 문서 업로드 & 파이프라인 실행"""

    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # 파일 저장
    doc_id = f"doc_{uuid.uuid4().hex}"
    saved_path = uploads_dir / f"{doc_id}_{file.filename}"

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 문서 메타데이터 DB 저장
    metadata = doc_service.create(
        doc_id=doc_id,
        org_filename=file.filename,
        user_id=user_id,
        dept_id=dept_id,
        project_id=project_id,
        category=category,
        file_type=Path(file.filename).suffix.lstrip("."),
        total_size=saved_path.stat().st_size
    )

    # Celery Worker에게 비동기 작업 전달
    task = process_document.apply_async(
        args=[str(saved_path), metadata]
    )

    return {
        "task_id": task.id,
        "doc_id": doc_id,
        "message": "문서 처리 시작"
    }


from celery.result import AsyncResult
from app.core.celery_app import celery_app

@router.get("/status/{task_id}")
def get_status(task_id: str):
    """문서 처리 상태 조회"""
    res = AsyncResult(task_id, app=celery_app)

    return {
        "task_id": task_id,
        "state": res.state,
        "info": res.info
    }

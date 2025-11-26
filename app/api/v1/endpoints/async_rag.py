# app/api/v1/endpoints/async_rag.py

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pathlib import Path
import shutil
import uuid
from celery.result import AsyncResult

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.tasks.rag_tasks import process_document
from app.services.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/api/v1", tags=["Async-RAG"])
settings = get_settings()


# --------- 1) 업로드 & 비동기 처리 시작 ---------
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    dept_id: str = Form(...),
    project_id: str = Form(...),
    category: str = Form(...),
):
    # 파일 저장
    uploads_dir = Path(settings.UPLOAD_DIR)
    uploads_dir.mkdir(parents=True, exist_ok=True)

    doc_id = f"doc_{Path(file.filename).stem}"
    saved_path = uploads_dir / f"{uuid.uuid4().hex}_{file.filename}"

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    metadata = {
        "doc_name": file.filename,
        "doc_id": doc_id,
        "user_id": user_id,
        "dept_id": dept_id,
        "project_id": project_id,
        "category": category,
        "file_type": Path(file.filename).suffix.lstrip("."),
        "total_size": saved_path.stat().st_size,
    }

    # Celery 작업 큐 등록
    task = process_document.apply_async(
        args=[str(uuid.uuid4()), str(saved_path), metadata]
    )

    return {
        "task_id": task.id,
        "message": "문서 처리 시작. 진행 상황을 확인하세요.",
    }


# --------- 2) 상태 조회 ---------
@router.get("/status/{task_id}")
def get_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)

    if result.state == "PENDING":
        # 큐에 들어갔지만 아직 시작 안 됨
        meta = {"current_step": "대기 중...", "progress": 0}
    else:
        meta = result.info if isinstance(result.info, dict) else {}

    resp = {
        "task_id": task_id,
        "status": result.state.lower(),
    }
    resp.update(meta)
    return resp


# --------- 3) 질의응답 ---------
class QueryRequest(BaseModel):
    query: str
    top_k: int | None = 5


@router.post("/query")
def rag_query(req: QueryRequest):
    try:
        pipeline = RAGPipeline()
        result = pipeline.query(req.query, top_k=req.top_k or 5)
        # pipeline.query는 이미 answer+sources 형태 반환 :contentReference[oaicite:4]{index=4}
        return result
    except Exception as e:
        raise HTTPException(500, f"RAG query failed: {e}")

# app/api/v1/endpoints/async_doc.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import shutil
from datetime import datetime
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

# ==========================================================
# 1) 일반 사용자 업로드 (승인 필요)
# ==========================================================
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    dept_id: int = Form(...),
    project_id: int = Form(...),
    category: str = Form(...),
    version: str = Form(...)
):
    """
    일반 사용자 업로드 API
    - 파일 저장만 수행
    - documents 테이블에 PENDING 으로 저장
    - 승인 필요
    """

    # ---------- 1. doc_id 생성 ----------
    clean_name = Path(file.filename).stem.replace(" ", "_")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    doc_id = f"{clean_name}_{ts}"

    # ---------- 2. 저장 경로 통일 ----------
    # uploads/global/{doc_id}/original.ext
    base_dir = Path(settings.UPLOAD_DIR) / "global" / doc_id
    base_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix.lower()
    saved_path = base_dir / f"original{file_ext}"

    # Write file
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 상대 경로 (DB 저장용)
    rel_path = saved_path.relative_to(settings.UPLOAD_DIR)

    # ---------- 3. DB 저장 ----------
    new_doc = doc_service.create(
        doc_id=doc_id,
        original_filename=file.filename,
        user_id=user_id,
        dept_id=dept_id,
        project_id=project_id,
        category=category,
        stored_path=str(rel_path),
        file_ext=file_ext.lstrip("."),
        version=version,
        status="PENDING"
    )

    return {
        "id": new_doc.get("id"),
        "doc_id": doc_id,
        "stored_path": str(rel_path),
        "status": "PENDING",
        "message": "문서 업로드 완료. 승인 대기 중입니다."
    }



# ==========================================================
# 2) 상태 조회 (Celery)
# ==========================================================
@router.get("/status/{task_id}")
def get_status(task_id: str):
    """
    Celery Task 상태 조회
    """
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.state,
        "info": result.info
    }



# ==========================================================
# 3) RAG 검색
# ==========================================================
class QueryRequest(BaseModel):
    query: str
    top_k: int | None = 5


@router.post("/query")
def rag_query(req: QueryRequest):
    """
    RAG 검색 API
    """
    try:
        pipeline = RAGPipeline()
        result = pipeline.query(req.query, top_k=req.top_k or 5)
        return result
    except Exception as e:
        raise HTTPException(500, f"RAG query failed: {e}")

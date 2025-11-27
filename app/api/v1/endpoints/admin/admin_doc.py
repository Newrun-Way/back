# app/api/v1/endpoints/admin/admin_doc.py
from fastapi import APIRouter, HTTPException
from app.services.document.document_service import DocumentService
from app.tasks.rag_tasks import process_document
from pathlib import Path
import json

router = APIRouter(prefix="/admin", tags=["Document Admin"])

doc_service = DocumentService()

@router.post("/approve/{doc_id}")
def approve_document(doc_id: str):
    """
    관리자 승인 → PROCESSING 상태 업데이트 → Celery Task 실행
    """
    doc = doc_service.get_by_external_doc_id(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    if doc["status"] != "PENDING":
        raise HTTPException(400, f"승인할 수 없는 상태입니다: {doc['status']}")

    # 상태 PROCESSING 으로 변경
    doc_service.update_status(doc_id, "PROCESSING")

    # Celery Task 실행
    stored_path = Path(doc["stored_path"])
    file_path = Path("data/uploads") / stored_path

    metadata_dict = {
        "doc_id": doc["external_doc_id"],
        "user_id": doc["user_id"],
        "dept_id": doc["dept_id"],
        "project_id": doc["project_id"],
        "category": doc["category"],
    }

    task = process_document.apply_async(
        args=[str(file_path), metadata_dict]
    )

    return {
        "task_id": task.id,
        "message": "문서 파싱/임베딩 작업을 시작했습니다."
    }

@router.post("/reject/{doc_id}")
def reject_document(doc_id: str):
    doc = doc_service.get_by_external_doc_id(doc_id)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    if doc["status"] != "PENDING":
        raise HTTPException(400, f"PENDING 상태만 반려 가능합니다.")

    doc_service.update_status(doc_id, "REJECTED")

    return {"message": "문서가 반려되었습니다."}


# app/api/v1/endpoints/requests.py

from fastapi import APIRouter, HTTPException
from pathlib import Path
from app.services.request.request_service import RequestService
from app.services.document.document_service import DocumentService
from app.tasks.rag_tasks import process_document
from app.core.config import get_settings
from .requests_dto import RequestCreateDTO, RejectDTO
import os
import shutil

router = APIRouter(prefix="/requests", tags=["Requests"])

req_service = RequestService()
doc_service = DocumentService()
settings = get_settings()


# ------------------------------- #
# 1) 요청 생성
# ------------------------------- #
@router.post("/")
def create_request(payload: RequestCreateDTO):
    req_id = req_service.create(
        requester_id=payload.requester_id,
        project_id=payload.project_id,
        request_type=payload.request_type,
        target_document_id=payload.target_document_id,
        content=payload.content
    )
    return {"request_id": req_id, "status": "PENDING"}


# ------------------------------- #
# 2) 승인 (관리자)
# ------------------------------- #
@router.post("/{req_id}/approve")
def approve_request(req_id: int):
    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    if req["status"] != "PENDING":
        raise HTTPException(400, "이미 처리된 요청입니다.")

    req_type = req["request_type"]
    target_doc_id = req["target_document_id"]

    # --- CREATE ---
    if req_type == "CREATE":
        # documents 테이블에서 해당 문서 조회
        doc = doc_service.get(target_doc_id)
        if not doc:
            raise HTTPException(404, "Target document not found")

        # 문서 상태 → PROCESSING
        doc_service.update_status(doc["external_doc_id"], "PROCESSING")

        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        # Celery 파싱 Task 실행
        metadata = {
            "doc_id": doc["external_doc_id"],
            "user_id": doc["user_id"],
            "dept_id": doc["dept_id"],
            "project_id": doc["project_id"],
            "category": doc["category"],
        }

        task = process_document.apply_async(args=[str(file_path), metadata])

        req_service.update_status(req_id, "APPROVED")

        return {"request_id": req_id, "task_id": task.id}

    # --- UPDATE ---
    if req_type == "UPDATE":
        if not target_doc_id:
            raise HTTPException(400, "UPDATE 요청에 target_document_id 필요")

        doc = doc_service.get(target_doc_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")

        # 1) 기존 문서 삭제 처리
        _delete_existing_document(doc)

        # 2) 새 문서 파일 파싱 (파일명은 동일 doc_id로 업로드 되었다고 가정)
        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        doc_service.update_status(doc["external_doc_id"], "PROCESSING")

        metadata = {
            "doc_id": doc["external_doc_id"],
            "user_id": doc["user_id"],
            "dept_id": doc["dept_id"],
            "project_id": doc["project_id"],
            "category": doc["category"],
        }

        task = process_document.apply_async(args=[str(file_path), metadata])
        req_service.update_status(req_id, "APPROVED")
        return {"request_id": req_id, "task_id": task.id}

    # --- DELETE ---
    if req_type == "DELETE":
        if not target_doc_id:
            raise HTTPException(400, "DELETE 요청에 target_document_id 필요")

        doc = doc_service.get(target_doc_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")

        # 문서 삭제 마킹 + 벡터DB에서 제거
        _delete_existing_document(doc)

        req_service.update_status(req_id, "APPROVED")
        return {"request_id": req_id, "deleted": True}

    raise HTTPException(400, f"지원하지 않는 요청 타입: {req_type}")


# ------------------------------- #
# 3) 반려
# ------------------------------- #
@router.post("/{req_id}/reject")
def reject_request(req_id: int, dto: RejectDTO):
    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    if req["status"] != "PENDING":
        raise HTTPException(400, "이미 처리된 요청입니다.")

    req_service.update_status(req_id, "REJECTED", rejection_reason=dto.reason)
    return {"request_id": req_id, "status": "REJECTED"}


# ------------------------------- #
# 내부 헬퍼: 기존 문서 삭제 & 벡터 DB 제거
# ------------------------------- #
def _delete_existing_document(doc: dict):
    """
    UPDATE / DELETE 승인 시 기존 데이터 제거
    """
    doc_id = doc["external_doc_id"]

    # 1) 파일 삭제
    file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]
    folder = file_path.parent
    if folder.exists():
        shutil.rmtree(folder)

    # 2) 벡터 DB에서 제거
    from app.services.rag.rag_service import RAGService
    rag = RAGService()

    col = rag.vector_store.collection
    col.delete(where={"external_doc_id": doc_id})

    # 3) DB 삭제 마킹
    doc_service.mark_deleted(doc_id)

# app/api/v1/endpoints/requests.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
from typing import Literal, Optional

from app.services.request.request_service import RequestService
from app.services.document.document_service import DocumentService
from app.services.document.document_cleaner import DocumentCleaner
from app.tasks.rag_tasks import process_document
from app.core.config import get_settings

router = APIRouter(prefix="/requests", tags=["Requests"])

req_service = RequestService()
doc_service = DocumentService()
settings = get_settings()
cleaner = DocumentCleaner()

# -------------------------------
# DTOs
# -------------------------------
class RequestCreateDTO(BaseModel):
    requester_id: int
    project_id: int
    request_type: Literal["CREATE", "UPDATE", "DELETE"]
    target_document_id: Optional[int] = None  # PK 기반
    content: Optional[str] = None


class RejectDTO(BaseModel):
    reason: str

# -------------------------------
# 1) 요청 생성
# -------------------------------
@router.post("/")
def create_request(payload: RequestCreateDTO):
    req_type = payload.request_type

    # UPDATE / DELETE는 반드시 target_document_id가 필요함
    if req_type in ("UPDATE", "DELETE") and not payload.target_document_id:
        raise HTTPException(400, f"{req_type} 요청에는 target_document_id(PK)가 필요합니다.")

    # CREATE에서 target_document_id는 FE가 반드시 준다고 가정
    if req_type == "CREATE" and not payload.target_document_id:
        raise HTTPException(400, "CREATE 요청에는 target_document_id(PK)가 필요합니다.")

    # 존재하는 문서인지 검사
    target_pk = payload.target_document_id
    if target_pk:
        doc = doc_service.get_by_id(target_pk)
        if not doc:
            raise HTTPException(404, "target_document_id(PK)에 해당하는 문서를 찾을 수 없습니다.")

    # 요청 생성
    req_id = req_service.create(
        requester_id=payload.requester_id,
        project_id=payload.project_id,
        request_type=req_type,
        target_document_id=target_pk,
        content=payload.content,
    )

    return {
        "request_id": req_id,
        "request_type": req_type,
        "target_document_id": target_pk,
        "status": "PENDING",
    }


# -------------------------------
# 2) 승인 (관리자)
# -------------------------------
@router.post("/{req_id}/approve")
def approve_request(req_id: int):
    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    if req["status"] != "PENDING":
        raise HTTPException(400, "이미 처리된 요청입니다.")

    req_type = req["request_type"]
    target_pk = req["target_document_id"]

    if not target_pk:
        raise HTTPException(400, f"{req_type} 요청에는 target_document_id(PK)가 필요합니다.")

    doc = doc_service.get_by_id(target_pk)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    external_doc_id = doc["external_doc_id"]

    metadata = {
        "doc_id": external_doc_id,
        "user_id": doc["user_id"],
        "dept_id": doc["dept_id"],
        "project_id": doc["project_id"],
        "category": doc["category"],
        "request_id": req_id,  # Celery에 넘겨서 후처리 쉽게
    }

    # -------------------- CREATE --------------------
    if req_type == "CREATE":
        if doc["status"] not in ("PENDING", "FAILED"):
            raise HTTPException(
                400,
                f"CREATE 승인 가능 상태가 아닙니다. 현재 상태: {doc['status']}",
            )

        doc_service.update_status(external_doc_id, "PROCESSING")

        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        task = process_document.apply_async(args=[str(file_path), metadata])
        req_service.save_task_id(req_id, task.id)
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "document_id": target_pk,
            "task_id": task.id,
            "message": "CREATE 승인: 파싱/임베딩 시작됨",
        }

    # -------------------- UPDATE --------------------
    if req_type == "UPDATE":
        cleaner.delete_vector(external_doc_id)
        doc_service.update_status(external_doc_id, "PROCESSING")

        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        task = process_document.apply_async(args=[str(file_path), metadata])
        req_service.save_task_id(req_id, task.id)
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "document_id": target_pk,
            "task_id": task.id,
            "message": "UPDATE 승인: 기존 벡터 삭제 후 재파싱 시작됨",
        }

    # -------------------- DELETE --------------------
    if req_type == "DELETE":
        cleaner.full_delete(doc)
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "document_id": target_pk,
            "deleted": True,
            "message": "DELETE 승인: 파일·벡터·DB 삭제 완료",
        }

    raise HTTPException(400, "지원하지 않는 요청 타입입니다.")


# -------------------------------
# 3) 반려
# -------------------------------
@router.post("/{req_id}/reject")
def reject_request(req_id: int, dto: RejectDTO):
    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    if req["status"] != "PENDING":
        raise HTTPException(400, "이미 처리된 요청입니다.")

    req_service.update_status(req_id, "REJECTED", rejection_reason=dto.reason)

    return {
        "request_id": req_id,
        "status": "REJECTED",
        "reason": dto.reason,
    }
# app/api/v1/endpoints/requests.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path

from app.services.request.request_service import RequestService
from app.services.document.document_service import DocumentService
from app.tasks.rag_tasks import process_document
from app.core.config import get_settings
from app.services.document.document_cleaner import DocumentCleaner

import os
import shutil

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
    request_type: str          # "CREATE" | "UPDATE" | "DELETE"
    target_document_id: str | None = None  # 여기서는 external_doc_id 사용 가정
    content: str | None = None


class RejectDTO(BaseModel):
    reason: str

# ------------------------------- #
# 1) 요청 생성
# ------------------------------- #
@router.post("/")
def create_request(payload: RequestCreateDTO):
    # request_type 검증
    if payload.request_type not in ("CREATE", "UPDATE", "DELETE"):
        raise HTTPException(400, "request_type must be one of CREATE/UPDATE/DELETE")

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
    target_doc_id = req["target_document_id"] #TODO : 키 확인 필요

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

        return {
            "request_id": req_id,
            "doc_id": doc["external_doc_id"],
            "task_id": task.id,
            "message": "CREATE 요청 승인, 파싱/임베딩 시작",
        }

    # --- UPDATE ---
    if req_type == "UPDATE":
        if not target_doc_id:
            raise HTTPException(400, "UPDATE 요청에 target_document_id 필요")

        doc = doc_service.get(target_doc_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")

        # 1) 기존 벡터 데이터 삭제 (파일/DB는 유지)
        cleaner.delete_vector(doc["external_doc_id"])

        # 2) 상태 → PROCESSING
        doc_service.update_status(doc["external_doc_id"], "PROCESSING")

        # 3) 현재 stored_path 기준으로 재파싱
        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        metadata = {
            "doc_id": doc["external_doc_id"],
            "user_id": doc["user_id"],
            "dept_id": doc["dept_id"],
            "project_id": doc["project_id"],
            "category": doc["category"],
        }

        task = process_document.apply_async(args=[str(file_path), metadata])

        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "doc_id": doc["external_doc_id"],
            "task_id": task.id,
            "message": "UPDATE 요청 승인, 기존 벡터 삭제 후 재파싱/임베딩 시작",
        }

    # --- DELETE ---
    if req_type == "DELETE":
        if not target_doc_id:
            raise HTTPException(400, "DELETE 요청에 target_document_id 필요")

        doc = doc_service.get(target_doc_id)
        if not doc:
            raise HTTPException(404, "문서를 찾을 수 없습니다.")

        # 문서 삭제 마킹 + 벡터DB에서 제거
        cleaner.full_delete(doc)

        req_service.update_status(req_id, "APPROVED")
        return {
            "request_id": req_id,
            "doc_id": doc["external_doc_id"],
            "deleted": True,
            "message": "DELETE 요청 승인, 문서 및 벡터/파일/DB 상태 정리 완료",
        }

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
    return {"request_id": req_id, "status": "REJECTED","reason": dto.reason}


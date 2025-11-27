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
    target_document_id: Optional[int] = None
    content: Optional[str] = None


class RejectDTO(BaseModel):
    reason: str

# ------------------------------- #
# 1) 요청 생성
# ------------------------------- #
@router.post("/")
def create_request(payload: RequestCreateDTO):
    """
    변경 요청 생성 API

    - request_type:
        - CREATE : 신규 문서 승인 요청
        - UPDATE : 기존 문서 수정 반영 요청
        - DELETE : 기존 문서 삭제 요청

    - target_document_id:
        - PK (documents.id) 기준
        - CREATE:
            - 지정하면 그 문서에 대한 '등록 승인' 요청
            - 지정 안 하면 (None) → requester_id + project_id 기준 최근 PENDING 문서를 자동 매칭 시도
        - UPDATE / DELETE:
            - 반드시 지정해야 함
    """
    req_type = payload.request_type
    target_doc_pk: Optional[int] = payload.target_document_id

    # --- 타입 검증 ---
    if req_type not in ("CREATE", "UPDATE", "DELETE"):
        raise HTTPException(400, "request_type must be one of CREATE/UPDATE/DELETE")

    # --- CREATE: target_document_id 없으면 자동 매칭 ---
    # if req_type == "CREATE":
    #     if target_doc_pk is None:
    #         # 사용자 + 프로젝트 기준 최근 PENDING 문서를 찾는다.
    #         pending_doc = doc_service.get_latest_pending_for_user_project(
    #             user_id=payload.requester_id,
    #             project_id=payload.project_id,
    #         )
    #         if not pending_doc:
    #             raise HTTPException(
    #                 400,
    #                 "CREATE 요청을 위한 PENDING 문서를 찾을 수 없습니다. "
    #                 "업로드가 선행되었는지 확인해주세요.",
    #             )
    #         target_doc_pk = pending_doc["id"]

    # --- UPDATE / DELETE: target_document_id 반드시 필요 ---
    if req_type in ("UPDATE", "DELETE") and not target_doc_pk:
        raise HTTPException(400, f"{req_type} 요청에는 target_document_id(PK)가 필요합니다.")

    # 존재하는 문서인지 한 번 검증 (CREATE/UPDATE/DELETE 모두)
    if target_doc_pk:
        doc = doc_service.get_by_id(target_doc_pk)
        if not doc:
            raise HTTPException(404, "target_document_id에 해당하는 문서를 찾을 수 없습니다.")

    # Request 생성
    req_id = req_service.create(
        requester_id=payload.requester_id,
        project_id=payload.project_id,
        request_type=req_type,
        target_document_id=target_doc_pk,
        content=payload.content,
    )

    return {
        "request_id": req_id,
        "request_type": req_type,
        "target_document_id": target_doc_pk,
        "status": "PENDING",
    }


# ------------------------------- #
# 2) 승인 (관리자)
# ------------------------------- #
@router.post("/{req_id}/approve")
def approve_request(req_id: int):
    """
    요청 승인 API (유일한 승인 엔진)
    - CREATE : 문서 등록 승인 → PROCESSING → Celery 파싱/임베딩
    - UPDATE : 기존 벡터 삭제 → PROCESSING → Celery 재파싱/임베딩
    - DELETE : 파일/벡터/DB 삭제
    """

    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    if req["status"] != "PENDING":
        raise HTTPException(400, "이미 처리된 요청입니다.")

    req_type = req["request_type"]
    target_doc_pk: Optional[int] = req["target_document_id"]

    if req_type not in ("CREATE", "UPDATE", "DELETE"):
        raise HTTPException(400, f"지원하지 않는 요청 타입입니다: {req_type}")

    if not target_doc_pk:
        raise HTTPException(400, f"{req_type} 요청에 target_document_id(PK)가 설정되어 있지 않습니다.")

    # documents.id 기준으로 문서 조회
    doc = doc_service.get_by_id(target_doc_pk)
    if not doc:
        raise HTTPException(404, "문서를 찾을 수 없습니다.")

    external_doc_id = doc["external_doc_id"]

    # 공통 metadata
    metadata = {
        "doc_id": external_doc_id,
        "user_id": doc["user_id"],
        "dept_id": doc["dept_id"],
        "project_id": doc["project_id"],
        "category": doc["category"],
    }

    # -------------------- CREATE --------------------
    if req_type == "CREATE":
        if doc["status"] not in ("PENDING", "FAILED"):
            raise HTTPException(
                400,
                f"CREATE 승인 가능 상태가 아닙니다. 현재 상태: {doc['status']}",
            )

        # 1) 상태 → PROCESSING
        doc_service.update_status(external_doc_id, "PROCESSING")

        # 2) 파일 경로
        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        # 3) Celery 파싱/임베딩 시작
        task = process_document.apply_async(args=[str(file_path), metadata])

        # 4) 요청 상태 업데이트
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "request_type": req_type,
            "document_id": target_doc_pk,
            "external_doc_id": external_doc_id,
            "task_id": task.id,
            "message": "CREATE 요청 승인: 문서 파싱/임베딩을 시작했습니다.",
        }

    # -------------------- UPDATE --------------------
    if req_type == "UPDATE":
        # 1) 기존 벡터 데이터 삭제 (파일/DB는 유지)
        cleaner.delete_vector(external_doc_id)

        # 2) 상태 → PROCESSING
        doc_service.update_status(external_doc_id, "PROCESSING")

        # 3) 현재 stored_path 기준으로 재파싱
        file_path = Path(settings.UPLOAD_DIR) / doc["stored_path"]

        task = process_document.apply_async(args=[str(file_path), metadata])

        # 4) 요청 상태 갱신
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "request_type": req_type,
            "document_id": target_doc_pk,
            "external_doc_id": external_doc_id,
            "task_id": task.id,
            "message": "UPDATE 요청 승인: 기존 벡터 삭제 후 재파싱/임베딩을 시작했습니다.",
        }

    # -------------------- DELETE --------------------
    if req_type == "DELETE":
        # 1) 파일/폴더 삭제 + 벡터 삭제 + DB mark_deleted
        cleaner.full_delete(doc)

        # 2) 요청 상태 갱신
        req_service.update_status(req_id, "APPROVED")

        return {
            "request_id": req_id,
            "request_type": req_type,
            "document_id": target_doc_pk,
            "external_doc_id": external_doc_id,
            "deleted": True,
            "message": "DELETE 요청 승인: 문서 및 벡터/파일/DB 상태 정리 완료",
        }

    # 여기까지 올 일은 없지만, 방어 코드
    raise HTTPException(400, f"지원하지 않는 요청 타입입니다: {req_type}")


# -------------------------------
# 3) 반려
# -------------------------------
@router.post("/{req_id}/reject")
def reject_request(req_id: int, dto: RejectDTO):
    """
    요청 반려 API
    - requests.status만 REJECTED로 변경
    - documents.status는 변경하지 않음 (문서 상태 유지)
    """
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
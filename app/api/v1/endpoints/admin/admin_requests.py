#app/api/v1/endpoints/admin_requests.py

from fastapi import APIRouter, HTTPException
from app.services.request.request_service import RequestService
from app.services.document.document_service import DocumentService

router = APIRouter(prefix="/admin/requests", tags=["admin"])

req_service = RequestService()
doc_service = DocumentService()


# ---------------------------------------
# 1) 요청 리스트 조회
# ---------------------------------------
@router.get("/")
def list_requests(status: str | None = None):
    """
    모든 요청 목록 조회 (상태 필터 가능)
    """
    rows = req_service.list(status=status)
    return {"count": len(rows), "items": rows}


# ---------------------------------------
# 2) 특정 요청 상세
# ---------------------------------------
@router.get("/{req_id}")
def get_request_detail(req_id: int):
    req = req_service.get(req_id)
    if not req:
        raise HTTPException(404, "Request not found")

    doc = None
    if req["target_document_id"]:
        doc = doc_service.get_by_id(req["target_document_id"])

    return {
        "request": req,
        "document": doc,
    }


# ---------------------------------------
# 3) 진행 중인 작업 리스트(PROCESSING + APPROVED)
# ---------------------------------------
@router.get("/tasks/in-progress")
def get_in_progress_tasks():
    """
    documents.status = PROCESSING
    또는 requests.status = APPROVED 인 작업 목록
    """
    docs = doc_service.list_by_status("PROCESSING")
    reqs = req_service.list(status="APPROVED")

    return {
        "documents_processing": docs,
        "requests_approved": reqs,
        "count": len(docs) + len(reqs)
    }


# ---------------------------------------
# 4) 실패한 작업 리스트
# ---------------------------------------
@router.get("/tasks/failed")
def get_failed_tasks():
    docs_failed = doc_service.list_by_status("FAILED")
    reqs_failed = req_service.list(status="FAILED")

    return {
        "documents_failed": docs_failed,
        "requests_failed": reqs_failed,
        "count": len(docs_failed) + len(reqs_failed)
    }


# ---------------------------------------
# 5) 문서 + 요청 전체 Overview
# ---------------------------------------
@router.get("/overview")
def admin_overview():
    docs = doc_service.list_all()
    reqs = req_service.list()

    return {
        "documents": docs,
        "requests": reqs,
        "documents_count": len(docs),
        "requests_count": len(reqs)
    }

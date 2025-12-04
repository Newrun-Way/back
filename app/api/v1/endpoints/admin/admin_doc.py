#app/api/v1/endpoints/admin/admin_doc.py
from fastapi import APIRouter, HTTPException
from app.services.document.document_service import DocumentService
from app.services.document.document_cleaner import DocumentCleaner

doc_service = DocumentService()
cleaner = DocumentCleaner()

router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/documents")
def admin_list_documents():
    return doc_service.list_all()

@router.get("/documents/{doc_pk}")
def admin_get_document(doc_pk: int):
    return doc_service.get_by_id(doc_pk)

# 문서 완전 삭제 API
@router.delete("/documents/{doc_pk}")
def admin_delete_document(doc_pk: str):
    """
    관리자 문서 삭제(파일 + 벡터DB + SQL 삭제 마킹)
    """
    # 1) 문서 메타데이터 존재 확인
    doc = doc_service.get_by_id(doc_pk)
    if not doc:
        raise HTTPException(404, "해당 문서를 찾을 수 없습니다.")

    # 2) 전체 삭제 실행
    cleaner.full_delete(doc)

    return {
        "doc_id": doc_pk,
        "message": "문서가 완전히 삭제되었습니다. (파일/벡터DB/DB)"
    }

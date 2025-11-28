#app/api/v1/endpoints/admin/admin_doc.py
from fastapi import APIRouter
from app.services.document.document_service import DocumentService

doc_service = DocumentService()
router = APIRouter(prefix="/admin", tags=["admin"])

@router.get("/documents")
def admin_list_documents():
    return doc_service.list_all()

@router.get("/documents/{doc_pk}")
def admin_get_document(doc_pk: int):
    return doc_service.get_by_id(doc_pk)
# app/services/document/document_cleaner.py

from pathlib import Path
import shutil
from app.services.document.document_service import DocumentService
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService

settings = get_settings()


class DocumentCleaner:

    def __init__(self):
        self.doc_service = DocumentService()

    def delete_file_folder(self, stored_path: str):
        """
        stored_path = "global/{doc_id}/original.hwp" 형식
        → 해당 doc_id 폴더 전체 삭제
        """
        full_path = Path(settings.UPLOAD_DIR) / stored_path
        folder = full_path.parent

        if folder.exists():
            shutil.rmtree(folder)

    def delete_vector(self, external_doc_id: str):
        """
        vector store 내 해당 문서 chunk 전체 삭제
        """
        rag = RAGService()
        col = rag.vector_store.collection
        col.delete(where={"external_doc_id": external_doc_id})

    def full_delete(self, doc: dict):
        """
        UPDATE나 DELETE 승인 시 필요한 전체 삭제 로직
        """
        stored_path = doc["stored_path"]
        doc_id = doc["external_doc_id"]

        # 1) 파일 삭제
        self.delete_file_folder(stored_path)

        # 2) 벡터 DB 삭제
        self.delete_vector(doc_id)

        # 3) DB 삭제 마킹
        self.doc_service.mark_deleted(doc_id)

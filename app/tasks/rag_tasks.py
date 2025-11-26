# app/tasks/rag_tasks.py

from celery import shared_task
from app.services.rag.rag_service import RAGService
from app.core.parser import parse_document
from app.services.document.document_service import DocumentService

doc_service = DocumentService()

@shared_task(bind=True, name="rag.process_document")
def process_document(self, file_path: str, metadata: dict):
    """
    파싱 → 청킹 → 임베딩 Celery Task
    """
    doc_id = metadata["doc_id"]

    try:
        # 상태는 approve()에서 이미 PROCESSING 으로 설정됨

        # 1) 파싱
        self.update_state(state="PROCESSING", meta={"step": "파싱 중..."})

        parsed = parse_document(
            file_path,
            doc_id=metadata["doc_id"],
            user_id=metadata["user_id"],
            dept_id=metadata["dept_id"],
            project_id=metadata["project_id"],
            category=metadata["category"]
        )

        # 2) 임베딩
        self.update_state(state="PROCESSING", meta={"step": "임베딩 중..."})

        rag = RAGService()
        rag.index_parsed_paragraphs_sharded(parsed, persist=True)

        # 3) 완료 상태 업데이트
        doc_service.update_status(doc_id, "PARSED")

        return {
            "status": "PARSED",
            "doc_id": doc_id,
            "message": "문서 파싱 및 임베딩 완료"
        }

    except Exception as e:
        # 실패 상태 업데이트
        doc_service.update_status(doc_id, "FAILED")
        raise e

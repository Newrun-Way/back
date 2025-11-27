# app/tasks/rag_tasks.py

from celery import shared_task
from pathlib import Path
import traceback

from app.services.document.document_service import DocumentService
from app.services.rag.pipeline import RAGPipeline
from app.services.request.request_service import RequestService
from app.core.config import get_settings

settings = get_settings()


@shared_task(bind=True)
def process_document(self, file_path: str, metadata: dict):
    """
    문서 파싱 + 임베딩 + vector 저장 Celery Task
    승인 엔진과 연결되도록 requests.status / documents.status 모두 업데이트한다.

    metadata 필드:
      - doc_id: external_doc_id (폴더명)
      - request_id: 승인 요청 id   <-- 매우 중요!
      - user_id / project_id / category …
    """

    doc_id = metadata.get("doc_id")
    request_id = metadata.get("request_id")    # ★ 승인 엔진 연동 핵심
    doc_service = DocumentService()
    req_service = RequestService()

    try:
        # 1) 파일 존재 확인
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        # 2) 문서 파이프라인 실행
        pipeline = RAGPipeline()
        chunks = pipeline.parse_document(str(path))
        pipeline.index_parsed_paragraphs_sharded(chunks, metadata)

        # 3) 문서 상태 = PARSED
        doc_service.update_status(doc_id, "PARSED")

        # 4) 요청 상태 = DONE
        if request_id:
            req_service.update_status(request_id, "DONE", rejection_reason=None, error_message=None)

        return {
            "doc_id": doc_id,
            "request_id": request_id,
            "chunks_indexed": len(chunks),
            "status": "SUCCESS"
        }

    except Exception as e:
        error_message = str(e)
        error_trace = traceback.format_exc()
        print("[Celery ERROR]", error_message)
        print(error_trace)

        # 5) 문서 상태 = FAILED
        try:
            doc_service.update_status(doc_id, "FAILED")
        except Exception as e2:
            print("[ERROR] 문서 상태 FAILED 업데이트 실패:", e2)

        # 6) 요청 상태 = FAILED + error_message 저장
        try:
            if request_id:
                req_service.update_status(
                    request_id,
                    "FAILED",
                    rejection_reason=None,
                    error_message=error_trace
                )
        except Exception as e3:
            print("[ERROR] 요청 상태 FAILED 업데이트 실패:", e3)

        return {
            "doc_id": doc_id,
            "request_id": request_id,
            "status": "FAILED",
            "error": error_message
        }

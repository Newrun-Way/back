# app/tasks/rag_tasks.py
import json
import redis
from celery import shared_task
from pathlib import Path
import traceback

from app.services.document.document_service import DocumentService
from app.services.request.request_service import RequestService
from app.core.parser import parse_document
from app.core.config import get_settings

settings = get_settings()
redis_client = redis.Redis.from_url(settings.REDIS_URL)


@shared_task(bind=True)
def process_document(self, file_path: str, metadata: dict):

    doc_id = metadata.get("doc_id")
    request_id = metadata.get("request_id")
    doc_service = DocumentService()
    req_service = RequestService()

    try:
        # 1) 파일 체크
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        # 2) 파싱
        meta = {
            "user_id": metadata.get("user_id"),
            "dept_id": metadata.get("dept_id"),
            "project_id": metadata.get("project_id"),
            "category": metadata.get("category"),
        }
        parsed = parse_document(
            str(path),
            doc_id=metadata["doc_id"],
            meta=meta,
        )
        from app.services.rag.rag_service import RAGService
        # 3) 청킹/임베딩
        rag = RAGService()
        rag.index_parsed_paragraphs_sharded(parsed, persist=True)

        # 4) 문서 상태 = PARSED
        doc_service.update_status(doc_id, "PARSED")

        # 5) 요청 상태 = DONE
        if request_id:
            req_service.update_status(request_id, "DONE")

        # 6) SSE publish — 성공 알림
        redis_client.publish(
            f"request-events:{request_id}",
            json.dumps({
                "status": "DONE",
                "doc_id": doc_id,
                "request_id": request_id,
            })
        )

        return {
            "doc_id": doc_id,
            "request_id": request_id,
            "chunks_indexed": len(parsed.get("paragraphs", [])),
            "status": "SUCCESS"
        }

    except Exception as e:
        error_message = str(e)
        error_trace = traceback.format_exc()

        # 문서 실패
        try:
            doc_service.update_status(doc_id, "FAILED")
        except:
            pass

        # 요청 실패
        try:
            if request_id:
                req_service.update_status(
                    request_id,
                    "FAILED",
                    error_message=error_trace
                )
        except:
            pass

        # 7) SSE publish — 실패 알림
        redis_client.publish(
            f"request-events:{request_id}",
            json.dumps({
                "status": "FAILED",
                "request_id": request_id,
                "error": error_message
            })
        )
        return {
            "doc_id": doc_id,
            "request_id": request_id,
            "status": "FAILED",
            "error": error_message
        }
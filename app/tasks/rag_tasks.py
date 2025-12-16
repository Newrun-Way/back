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

doc_service = DocumentService()
req_service = RequestService()

@shared_task(bind=True)
def process_document(self, file_path: str, metadata: dict):
    """
    파싱 → 청킹 → 임베딩 Celery Task
    """
    doc_id = metadata.get("doc_id")
    if not doc_id:
        raise ValueError("metadata['doc_id'](external_doc_id)가 필요합니다.")
    request_id = metadata.get("request_id")

    try:
        # 1) 파일 존재 확인
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        # 2) meta 구성
        meta = {
            "db_id": metadata.get("db_id"),
            "external_doc_id": metadata.get("external_doc_id") or doc_id,
            "user_id": metadata.get("user_id"),
            "dept_id": metadata.get("dept_id"),
            "project_id": metadata.get("project_id"),
            "category": metadata.get("category"),
            "version": metadata.get("version"),
            "upload_date": metadata.get("upload_date"),
            "filename": metadata.get("filename"),
            "file_ext": metadata.get("file_ext"),
            "file_path": metadata.get("file_path"),
        }
        # 3) 파싱
        parsed = parse_document(
            str(path),
            doc_id=meta["external_doc_id"],
            meta=meta,
        )

        # 4) 임베딩 / 인덱싱
        from app.services.rag.rag_service import RAGService

        rag = RAGService()
        rag.index_parsed_paragraphs_sharded(parsed, persist=True)

        # 5) 문서 상태 업데이트
        doc_service.update_status(doc_id, "PARSED")

        # 6) 요청 상태 업데이트
        if request_id:
            req_service.update_status(request_id, "DONE")

        # 7) SSE / Redis 알림 (✅ 반드시 channel + message 필요)
        redis_client.publish(
            "document_events",
            json.dumps({
                "type": "DOCUMENT_PARSED",
                "doc_id": doc_id,
                "request_id": request_id,
                "status": "PARSED",
            }, ensure_ascii=False)
        )

        return {
            "doc_id": doc_id,
            "status": "PARSED",
        }

    except Exception as e:
        err = traceback.format_exc()

        # ❌ 실패 상태 반영
        doc_service.update_status(doc_id, "FAILED")
        if request_id:
            req_service.save_error(request_id, str(e))

        redis_client.publish(
            "document_events",
            json.dumps({
                "type": "DOCUMENT_FAILED",
                "doc_id": doc_id,
                "request_id": request_id,
                "status": "FAILED",
                "error": str(e),
            }, ensure_ascii=False)
        )

        raise

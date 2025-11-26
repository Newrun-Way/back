# app/tasks/rag_tasks.py
from pathlib import Path
from datetime import datetime
from celery import states
from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.parser import parse_document
from app.services.rag.rag_service import RAGService

settings = get_settings()


@celery_app.task(bind=True, name="app.tasks.rag_tasks.process_document")
def process_document(self, task_id: str, file_path: str, metadata_dict: dict):
    """
    비동기 문서 처리 작업
    - 파일 파싱 (HWP/HWPX)
    - 청킹 및 임베딩
    - 벡터스토어 저장
    - (선택) extracted_results 디렉토리에 결과 저장
    """
    try:
        # 1단계: 파일 파싱
        self.update_state(
            state=states.STARTED,
            meta={"current_step": "파일 파싱 중...", "progress": 10},
        )

        doc_id = metadata_dict.get("doc_id") or Path(file_path).name
        meta = {
            **metadata_dict,
            "doc_id": doc_id,
            "created_at": datetime.utcnow().isoformat(),
        }

        parsed = parse_document(file_path, doc_id=doc_id, meta=meta)

        # 2단계: 인덱싱 (우리 RAGService 사용)
        self.update_state(
            state=states.STARTED,
            meta={"current_step": "청킹 및 임베딩 중...", "progress": 60},
        )

        rag = RAGService()
        rag.index_parsed_paragraphs_sharded(parsed, persist=True)

        # (옵션) 동료 구조 맞추려면 EXTRACTED_DIR에 결과 저장
        # extracted_dir = Path(settings.EXTRACTED_DIR) / doc_id
        # extracted_dir.mkdir(parents=True, exist_ok=True)
        # ... parsed를 json/txt로 저장해두면 owpml1 형식과 호환 가능 ...

        # 3단계: 완료
        self.update_state(
            state=states.SUCCESS,
            meta={"current_step": "완료", "progress": 100},
        )

        return {
            "status": "completed",
            "doc_id": doc_id,
            "message": "문서 처리 완료",
        }

    except Exception as e:
        self.update_state(
            state=states.FAILURE,
            meta={"error": str(e)},
        )
        raise

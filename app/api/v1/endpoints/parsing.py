from datetime import datetime
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import shutil
import logging

from app.core.config import get_settings
from app.core.parser import parse_document
from app.services.rag.rag_service import RAGService
from app.core.db import get_connection   # pymysql

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/upload-and-parse/")
async def upload_and_parse(
    file: UploadFile = File(...),

    # FE 메타
    user_id: int = Form(...),
    dept_id: Optional[int] = Form(None),
    project_id: Optional[int] = Form(None),
    category: Optional[str] = Form(None),
    version: Optional[str] = Form(None),
    upload_date: Optional[datetime] = Form(None),
):
    logger.info("=== [upload_and_parse] 요청 수신 ===")
    logger.info(f"수신 파일명: {file.filename}")
    logger.info(f"메타(user={user_id}, dept={dept_id}, project={project_id}, "
                f"category={category}, version={version}, upload_date={upload_date})")

    # 1) 확장자 검사
    if not file.filename.endswith((".hwp", ".hwpx")):
        logger.error("잘못된 확장자 업로드 감지")
        raise HTTPException(status_code=400, detail="Only .hwp/.hwpx allowed")

    # 2) 저장 경로 준비
    doc_id = file.filename                     # external_doc_id
    file_ext = Path(file.filename).suffix.lower()
    bucket = str(user_id)

    doc_dir = Path(settings.UPLOAD_DIR) / bucket / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    saved_path = doc_dir / f"original{file_ext}"

    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    logger.info(f"[FILE SAVE] {saved_path.resolve()} 저장 완료")

    # 3) 업로드 시간
    effective_upload_date = upload_date or datetime.utcnow()

    # 4) ------------------- DB INSERT -------------------
    conn = get_connection()
    cursor = conn.cursor()

    try:
        insert_sql = """
            INSERT INTO documents (
                external_doc_id, user_id, dept_id, project_id,
                category, version, upload_date,
                original_filename, stored_path, file_ext, status
            )
            VALUES (
                %(external_doc_id)s, %(user_id)s, %(dept_id)s, %(project_id)s,
                %(category)s, %(version)s, %(upload_date)s,
                %(original_filename)s, %(stored_path)s, %(file_ext)s, %(status)s
            )
        """

        params = {
            "external_doc_id": doc_id,
            "user_id": user_id,
            "dept_id": dept_id,
            "project_id": project_id,
            "category": category,
            "version": version,
            "upload_date": effective_upload_date,
            "original_filename": file.filename,
            "stored_path": str(saved_path.relative_to(settings.UPLOAD_DIR)),
            "file_ext": file_ext,
            "status": "PENDING",
        }

        cursor.execute(insert_sql, params)
        new_document_id = cursor.lastrowid
        conn.commit()

        logger.info(f"[DB INSERT] documents.id={new_document_id} INSERT 완료")

    except Exception as e:
        conn.rollback()
        logger.exception("[DB ERROR] 문서 INSERT 중 예외 발생")
        raise HTTPException(status_code=500, detail=f"DB Insert Error: {e}")

    finally:
        cursor.close()
        conn.close()

    # 5) 메타 구성
    meta = {
        "db_id": new_document_id,
        "external_doc_id": doc_id,
        "user_id": user_id,
        "dept_id": dept_id,
        "project_id": project_id,
        "category": category,
        "version": version,
        "upload_date": effective_upload_date.isoformat(),
        "filename": file.filename,
        "file_ext": file_ext,
        "file_path": str(saved_path.relative_to(settings.UPLOAD_DIR)),
    }

    logger.info(f"[META BUILD] meta={meta}")

    # 6) 파싱
    parsed = parse_document(str(saved_path), doc_id=str(doc_id), meta=meta)
    merged = parsed.get("metadata", {})
    merged.update(meta)
    parsed["metadata"] = merged

    logger.info(f"[PARSING COMPLETE] 총 paragraph={len(parsed.get('paragraphs', []))}")

    # 7) 인덱싱 (Chroma)
    rag = RAGService()
    indexed = rag.index_parsed_paragraphs_sharded(parsed, persist=True)

    logger.info(f"[CHROMA INDEX] 인덱싱된 청크 수: {indexed}")

    # --- 선택적 디버그: 인덱스 검사 ---
    try:
        test_debug = rag.search_with_shard(
            query="__debug__check__",  # 아무거나
            user_id=user_id,
            project_id=project_id,
            dept_id=dept_id,
            top_k=2
        )
        logger.info("[CHROMA DEBUG SEARCH] 검색 결과 샘플:")
        for item in test_debug:
            logger.info(f"  - {item}")
    except Exception as e:
        logger.warning(f"[CHROMA DEBUG] 검색 체크 중 예외 발생: {e}")

    # 8) DB 상태 업데이트
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "UPDATE documents SET status='PARSED' WHERE id=%s",
            (new_document_id,)
        )
        conn.commit()
        logger.info(f"[DB UPDATE] documents.id={new_document_id} status=PARSED 변경")

    except Exception as e:
        conn.rollback()
        logger.exception("[DB ERROR] 상태 업데이트 중 에러")
        raise HTTPException(status_code=500, detail=f"DB Update Error: {e}")

    finally:
        cursor.close()
        conn.close()

    # 9) 응답
    logger.info("=== [upload_and_parse] 완료 ===")

    return {
        "document_id": new_document_id,
        "external_doc_id": doc_id,
        "filename": file.filename,
        "saved_path": str(saved_path),
        "indexed_chunks": indexed,
        "metadata": parsed["metadata"],
        "debug": {
            "file_saved": str(saved_path),
            "db_inserted_id": new_document_id,
            "chunk_indexed_count": indexed,
        }
    }

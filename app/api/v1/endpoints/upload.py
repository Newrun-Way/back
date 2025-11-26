from datetime import datetime
from typing import Optional
from pathlib import Path
import shutil
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.core.config import get_settings
from app.core.db import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()


@router.post("/upload/", summary="문서 단순 업로드 (승인 대기용)")
async def upload_document(
        file: UploadFile = File(...),

        # 메타데이터 (FE에서 전송)
        user_id: int = Form(...),
        dept_id: Optional[int] = Form(None),
        project_id: Optional[int] = Form(None),
        category: Optional[str] = Form(None),
        version: Optional[str] = Form(None),
        upload_date: Optional[datetime] = Form(None),
):
    """
    1. 파일을 'global' 폴더에 저장
    2. DB에 메타데이터 저장 (Status='PENDING')
    3. 파싱/인덱싱은 수행하지 않음 (관리자 승인 후 별도 수행)
    """
    logger.info(f"=== [Upload Request] File: {file.filename}, User: {user_id} ===")

    # 1) 확장자 검사
    if not file.filename.endswith((".hwp", ".hwpx")):
        raise HTTPException(status_code=400, detail="Only .hwp/.hwpx allowed")

    # 2) 저장 경로 설정 (Global 폴더 사용)
    doc_id = file.filename
    file_ext = Path(file.filename).suffix.lower()

    # [중요] 모든 파일은 물리적으로 'global' 폴더에 저장
    bucket = "global"
    doc_dir = Path(settings.UPLOAD_DIR) / bucket / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    saved_path = doc_dir / f"original{file_ext}"

    # 3) 파일 저장
    try:
        with open(saved_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        logger.info(f"[FILE SAVED] Path: {saved_path}")
    except Exception as e:
        logger.error(f"File save failed: {e}")
        raise HTTPException(status_code=500, detail="File save failed")

    # 4) DB Insert
    effective_upload_date = upload_date or datetime.utcnow()
    stored_path_rel = str(saved_path.relative_to(settings.UPLOAD_DIR))  # DB에는 상대 경로 저장

    conn = get_connection()
    cursor = conn.cursor()

    try:
        insert_sql = """
            INSERT INTO documents (
                external_doc_id, user_id, dept_id, project_id,
                category, version, upload_date,
                original_filename, stored_path, file_ext, 
                status
            )
            VALUES (
                %(external_doc_id)s, %(user_id)s, %(dept_id)s, %(project_id)s,
                %(category)s, %(version)s, %(upload_date)s,
                %(original_filename)s, %(stored_path)s, %(file_ext)s, 
                %(status)s
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
            "stored_path": stored_path_rel,
            "file_ext": file_ext,

            # [중요] 아직 파싱되지 않았으므로 PENDING 상태
            # 승인 대기중이라는 의미로 'WAITING_APPROVAL' 같은 코드를 써도 좋습니다.
            "status": "PENDING",
        }

        cursor.execute(insert_sql, params)
        new_doc_id = cursor.lastrowid
        conn.commit()

        logger.info(f"[DB INSERT] Document ID: {new_doc_id} (Status: PENDING)")

    except Exception as e:
        conn.rollback()
        logger.error(f"[DB ERROR] Insert failed: {e}")
        # 파일은 저장됐는데 DB 실패하면 파일도 지우는게 깔끔하지만, 여기선 에러만 반환
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    finally:
        cursor.close()
        conn.close()

    return {
        "message": "Upload successful. Waiting for approval.",
        "document_id": new_doc_id,
        "filename": file.filename,
        "status": "PENDING"
    }
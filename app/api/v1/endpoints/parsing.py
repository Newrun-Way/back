from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from pathlib import Path
import shutil, os
from app.core.config import get_settings
from app.core.parser import parse_document
from app.services.rag.rag_service import RAGService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()
# print("세팅은 :",settings)

@router.post("/upload-and-parse/")
async def upload_and_parse_hwp(
    file: UploadFile = File(...),
    dept_id: str | None = Form(None),
    project_id: str | None = Form(None),
    user_id: str | None = Form(None)
):
    if not file.filename.endswith((".hwp", ".hwpx")):
        raise HTTPException(status_code=400, detail="Only .hwp/.hwpx allowed")

    # 1) 영구 저장 경로 생성
    doc_id = file.filename  # 필요시 uuid4로 대체: f"{uuid.uuid4().hex}_{file.filename}"
    bucket = user_id or "anonymous"
    doc_dir = Path(settings.UPLOAD_DIR) / bucket / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    saved_path = doc_dir / f"original{Path(file.filename).suffix.lower()}"

    # 2) 원본 저장
    with open(saved_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    # 3) 메타 통합
    meta = {
        "dept_id": dept_id,
        "project_id": project_id,
        "user_id": user_id,
        "doc_id": doc_id,
        "filename": file.filename,
        # 프론트에서 열람/다운로드 위해 상대 경로 저장
        "file_path": str(saved_path.relative_to(settings.UPLOAD_DIR)),
    }
    
    # 4) 파싱 (parser가 meta를 metadata로 병합하도록 수정되어 있어야 함)
    parsed = parse_document(str(saved_path), doc_id=doc_id, meta=meta)
    # 메타데이터 보강
    merged = parsed.get("metadata", {})
    merged.update(meta)
    parsed["metadata"] = merged
    
    # 5) 인덱싱 (샤드)
    rag = RAGService()
    indexed = rag.index_parsed_paragraphs_sharded(parsed, persist=True)
    logger.info(f"Saving uploaded file to: {saved_path.resolve()}")
    return {
        "filename": file.filename,
        "doc_id": doc_id,
        "metadata": parsed["metadata"],
        "indexed": indexed,
    }
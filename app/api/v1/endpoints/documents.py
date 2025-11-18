# app/api/v1/endpoints/documents.py

from fastapi import APIRouter
from pathlib import Path
from app.core.config import get_settings
import json

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()

@router.get("/")
def list_documents():
    base = Path(settings.UPLOAD_DIR)
    docs = []

    # 1-dept → user_id
    for user_dir in base.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name

        # 2-depth → doc_id
        for doc_dir in user_dir.iterdir():
            if not doc_dir.is_dir():
                continue

            doc_id = doc_dir.name

            # 파일 찾기
            files = [f.name for f in doc_dir.iterdir() if f.is_file()]

            docs.append({
                "user_id": user_id,
                "doc_id": doc_id,
                "files": files,
                "path": str(doc_dir)
            })

    return docs

@router.get("/{doc_id}")
def get_document(doc_id: str):
    base = Path(settings.UPLOAD_DIR)

    for user_dir in base.iterdir():
        if not user_dir.is_dir():
            continue
        for doc_dir in user_dir.iterdir():
            if doc_dir.name == doc_id:
                meta_path = doc_dir / "metadata.json"
                if meta_path.exists():
                    return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"error": "Not found"}

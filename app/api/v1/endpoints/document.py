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

    for user_dir in base.iterdir():
        for doc_dir in user_dir.iterdir():
            meta_path = doc_dir / "metadata.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
                docs.append(metadata)
    return docs


@router.get("/{doc_id}")
def get_document(doc_id: str):
    base = Path(settings.UPLOAD_DIR)
    for user_dir in base.iterdir():
        for doc_dir in user_dir.iterdir():
            if doc_dir.name == doc_id:
                meta_path = doc_dir / "metadata.json"
                if meta_path.exists():
                    return json.loads(meta_path.read_text(encoding="utf-8"))
    return {"error": "Not found"}

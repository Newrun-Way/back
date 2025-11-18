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

    # uploads/*/  ← user_id
    for user_dir in base.iterdir():
        if not user_dir.is_dir():
            continue

        user_id = user_dir.name

        # uploads/user_id/*  ← doc_id
        for doc_dir in user_dir.iterdir():
            if not doc_dir.is_dir():
                continue

            doc_id = doc_dir.name
            meta_path = doc_dir / "metadata.json"

            if meta_path.exists():
                try:
                    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
                except:
                    metadata = {"doc_id": doc_id, "user_id": user_id}

                # user_id, doc_id를 메타데이터에 덧붙여줌
                metadata.setdefault("doc_id", doc_id)
                metadata.setdefault("user_id", user_id)
                docs.append(metadata)

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

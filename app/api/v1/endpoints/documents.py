# app/api/v1/endpoints/documents.py

from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
from app.core.config import get_settings
import chromadb
import json

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()
GLOBAL_DIR_NAME = "global"

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
def get_document_detail(doc_id: str):
    """
    문서 상세 조회 (벡터 DB)
    - user_id 없이 doc_id로만 조회
    - 경로: settings.VECTOR_STORE_DIR / global
    """

    # 1) 샤드 위치: 이제 무조건 'global' 폴더를 바라봅니다.
    shard_path = Path(settings.VECTOR_STORE_DIR) / GLOBAL_DIR_NAME

    if not shard_path.exists():
        # global 샤드가 아예 없으면 500 또는 404 에러
        raise HTTPException(404, f"Global shard not found at {shard_path}")

    # 2) 크로마 클라이언트 로드
    client = chromadb.PersistentClient(path=str(shard_path))

    # 3) documents 컬렉션 로드
    try:
        col = client.get_collection("documents")
    except:
        raise HTTPException(404, "documents collection not found in global shard")

    # 4) 실제 필터 조건: user_id 조건 삭제, doc_id만 사용
    # (global DB에 user_id 메타데이터가 남아있더라도, 입력값이 없으므로 doc_id로만 찾습니다)
    result = col.get(
        where={"external_doc_id": doc_id},
        include=["documents", "metadatas"]
    )

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    if len(docs) == 0:
        return {
            "doc_id": doc_id,
            "chunks": [],
            "total_chunks": 0,
            "message": "Document not found in global shard"
        }

    # 5) chunk 순서 정렬
    items = list(zip(docs, metas))
    items.sort(key=lambda x: x[1].get("paragraph_idx", 0))

    # 6) 문서 merge
    merged = "\n".join([t[0] for t in items])

    return {
        "doc_id": doc_id,
        "total_chunks": len(items),
        "content": merged,
        "chunks": [
            {
                "paragraph_idx": meta.get("paragraph_idx"),
                "content": text,
                "metadata": meta
            }
            for text, meta in items
        ]
    }

@router.get("/download/{doc_id}", summary="문서 다운로드")
def download_document(doc_id: str):
    """
    문서 다운로드 (파일 시스템)
    - user_id 없이 doc_id로만 조회
    - 경로: settings.UPLOAD_DIR / global / {doc_id}
    """

    base = Path(settings.UPLOAD_DIR)

    # 1) 파일 경로: 무조건 'global' 폴더 안의 doc_id 폴더를 찾습니다.
    # 예: /data/upload/global/doc_12345/
    doc_dir = base / GLOBAL_DIR_NAME / doc_id

    if not doc_dir.exists() or not doc_dir.is_dir():
        raise HTTPException(404, f"Document folder not found: {doc_dir}")

    # 2) 원본 파일 찾기 (original.*)
    files = list(doc_dir.glob("original.*"))
    if not files:
        raise HTTPException(404, f"No original file found in folder: {doc_dir}")

    file_path = files[0]
    file_ext = file_path.suffix

    # 3) 다운로드 파일명 결정 로직
    if doc_id.lower().endswith(file_ext.lower()):
        download_name = doc_id
    else:
        download_name = f"{doc_id}{file_ext}"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/octet-stream"
    )
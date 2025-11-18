# app/api/v1/endpoints/documents.py

from fastapi import APIRouter,HTTPException
from pathlib import Path
from app.core.config import get_settings
import chromadb
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


@router.get("/{user_id}/{doc_id}")
def get_document_detail(user_id: str, doc_id: str):
    # 1) 샤드 디렉토리 위치 (폴더명은 'user=1' 그대로 사용)
    shard_path = Path(settings.VECTOR_STORE_DIR) / user_id
    if not shard_path.exists():
        raise HTTPException(404, f"Shard {user_id} not found")

    # 2) 크로마 클라이언트 로드
    client = chromadb.PersistentClient(path=str(shard_path))

    # 3) documents 컬렉션 로드
    try:
        col = client.get_collection("documents")
    except:
        raise HTTPException(404, "documents collection not found")

    # ==========================================
    # [수정됨] user_id 파싱 로직 개선
    # URL이 "user=1"로 들어오면 -> 숫자 1로 변환하여 검색
    # ==========================================
    search_user_id = user_id
    if isinstance(user_id, str) and user_id.startswith("user="):
        try:
            # "user=" 뒷부분을 잘라내고 숫자로 변환
            search_user_id = int(user_id.split("=")[1])
        except (IndexError, ValueError):
            # 변환 실패 시 원래 값 사용
            pass
    elif user_id.isdigit():
        search_user_id = int(user_id)

    # 4) 실제 필터 조건: user_id + external_doc_id 매칭
    result = col.get(
        where={
            "$and": [
                {"user_id": search_user_id},  # 수정된 search_user_id 사용
                {"external_doc_id": doc_id}
            ]
        },
        include=["documents", "metadatas"]
    )

    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    if len(docs) == 0:
        return {
            "user_id": user_id,
            "doc_id": doc_id,
            "chunks": [],
            "total_chunks": 0
        }

    # 5) chunk 순서 정렬
    items = list(zip(docs, metas))
    # paragraph_idx가 없을 경우를 대비해 안전하게 0 처리
    items.sort(key=lambda x: x[1].get("paragraph_idx", 0))

    # 6) 문서 merge
    merged = "\n".join([t[0] for t in items])

    return {
        "user_id": user_id,
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

@router.get("/download/{user_id}/{doc_id}", summary="문서 다운로드")
def download_document(user_id: str, doc_id: str):

    # 업로드 기본 경로
    base = Path(settings.UPLOAD_DIR)

    # 실제 문서가 저장된 위치
    doc_dir = base / user_id / doc_id

    if not doc_dir.exists() or not doc_dir.is_dir():
        raise HTTPException(404, f"Document folder not found: {doc_dir}")

    # 내부 파일명은 언제나 original.* 형태
    files = list(doc_dir.glob("original.*"))
    if not files:
        raise HTTPException(404, f"No original file found in folder: {doc_dir}")

    file_path = files[0]

    # 다운로드 파일명은 실제 doc_id로 반환되게 설정
    # 예: 뉴런웨이_과제테스트.hwpx
    download_name = f"{doc_id}{file_path.suffix}"

    return FileResponse(
        path=str(file_path),
        filename=download_name,
        media_type="application/octet-stream"
    )
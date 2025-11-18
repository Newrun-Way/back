# app/api/v1/endpoints/rag_admin.py
from fastapi import APIRouter
from pathlib import Path
import chromadb
from app.core.config import get_settings

router = APIRouter(prefix="/rag-admin", tags=["RAG-Admin"])
settings = get_settings()

@router.get("/dump")
def dump_all_chroma():
    """
    모든 샤드(user_id 기반) + 모든 컬렉션 + chunk 정보 요약을 한 번에 반환하는 관리자용 API.
    Swagger에서 바로 조회 가능.
    """
    base = Path(settings.VECTOR_STORE_DIR)
    shards = {}

    # 1) 샤드 디렉토리 스캔
    for shard_dir in base.iterdir():
        if not shard_dir.is_dir():
            continue

        shard_key = shard_dir.name
        shard_path = str(shard_dir)

        try:
            client = chromadb.PersistentClient(path=shard_path)
            collections = client.list_collections()
        except Exception as e:
            shards[shard_key] = {"error": f"Failed to load shard: {e}"}
            continue

        shard_info = {}

        # 2) 각 컬렉션 조회
        for col in collections:
            col_obj = client.get_collection(col.name)

            try:
                data = col_obj.get()
            except Exception as e:
                shard_info[col.name] = {"error": f"Failed col.get(): {e}"}
                continue

            docs = data.get("documents", [])
            metadatas = data.get("metadatas", [])
            ids = data.get("ids", [])
            embeddings = data.get("embeddings", [])

            # 3) preview-friendly 형태로 구성
            preview_items = []
            for i in range(len(docs)):
                doc_preview = docs[i][:200] + "..." if len(docs[i]) > 200 else docs[i]
                meta = metadatas[i] if i < len(metadatas) else {}
                preview_items.append({
                    "id": ids[i] if i < len(ids) else None,
                    "content_preview": doc_preview,
                    "metadata": meta,
                })

            shard_info[col.name] = {
                "collection_name": col.name,
                "total_chunks": len(docs),
                "preview": preview_items[:20],  # 너무 많으면 20개까지만 출력
                "embedding_size": len(embeddings[0]) if embeddings else 0,
            }

        shards[shard_key] = shard_info

    return {"shards": shards}
@router.get("/debug-scan/{shard}")
def debug_scan(shard: str):
    """
    특정 샤드 내부의 컬렉션 메타데이터 10개를 확인하는 디버그용 API
    실제 저장된 user_id, external_doc_id, paragraph_idx를 확인하는 목적
    """
    base = Path(settings.VECTOR_STORE_DIR)
    shard_path = base / shard

    if not shard_path.exists():
        return {"error": f"Shard not found: {shard_path}"}

    import chromadb
    client = chromadb.PersistentClient(path=str(shard_path))

    # 컬렉션 이름 자동 탐색
    collections = client.list_collections()
    info = {}

    for col in collections:
        c = client.get_collection(col.name)
        data = c.get(include=["metadatas"], limit=20)
        info[col.name] = data["metadatas"]

    return {
        "shard": shard,
        "collections": info
    }
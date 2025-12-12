# app/api/v1/endpoints/rag_admin.py
from fastapi import APIRouter, HTTPException
from pathlib import Path
import chromadb
from app.core.config import get_settings
from app.services.rag.rag_service import RAGService
from app.services.document.table_processor import TableProcessor

router = APIRouter(prefix="/rag-admin", tags=["dev"])
settings = get_settings()

@router.get("/dump")
def dump_all_chroma(limit: int = 5000):
    """
    ChromaDB 안의 전체 문서를 덤프해서 디버깅하는 API.
    external_doc_id mismatch 여부 확인 가능.
    """
    try:
        rag = RAGService()
        col = rag.vector_store.collection
    except Exception as e:
        raise HTTPException(500, f"Chroma 로드 실패: {e}")

    try:
        result = col.get(include=["documents", "metadatas"], limit=limit)
    except Exception as e:
        raise HTTPException(500, f"VectorStore get() 실패: {e}")

    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    dump = []

    for i in range(len(ids)):
        meta = metadatas[i] or {}
        doc_preview = ""

        if documents[i]:
            # 문서 첫 80자만 출력
            doc_preview = documents[i][:80].replace("\n", " ")

        dump.append({
            "idx": i,
            "id": ids[i],
            "external_doc_id": meta.get("external_doc_id"),
            "paragraph_idx": meta.get("paragraph_idx"),
            "project_id": meta.get("project_id"),
            "user_id": meta.get("user_id"),
            "category": meta.get("category"),
            "preview": doc_preview
        })

    return {
        "count": len(dump),
        "items": dump
    }

@router.get("/doc-chunks")
def get_doc_chunks(external_doc_id: str, limit: int = 1000):
    """
    특정 문서(external_doc_id)에 해당하는 chunk들을 직접 조회하는 개발용 API.
    - 현재 저장된 metadata key가 external_doc_id가 맞는지 확인 가능
    - 문제가 있다면 어떤 metadata로 저장돼 있는지 한눈에 파악 가능
    """
    try:
        rag = RAGService()
        col = rag.vector_store.collection
    except Exception as e:
        raise HTTPException(500, f"Chroma 로드 실패: {e}")

    # where 필터
    query_filter = {"external_doc_id": external_doc_id}

    try:
        result = col.get(
            where=query_filter,
            include=["documents", "metadatas"],
            limit=limit
        )
    except Exception as e:
        raise HTTPException(500, f"VectorStore get() 실패: {e}")

    ids = result.get("ids", [])
    documents = result.get("documents", [])
    metadatas = result.get("metadatas", [])

    items = []
    for i in range(len(ids)):
        doc_preview = (documents[i][:80].replace("\n", " ") if documents[i] else "")
        items.append({
            "id": ids[i],
            "external_doc_id": metadatas[i].get("external_doc_id"),
            "metadata": metadatas[i],
            "preview": doc_preview
        })

    return {
        "external_doc_id": external_doc_id,
        "count": len(items),
        "items": items
    }
@router.get("/debug/latest")
def debug_latest(limit: int = 300):
    """
    VectorDB에서 가장 최근 저장된 embedding을 확인하기 위한 디버그 엔드포인트.
    실제 external_doc_id가 어떻게 들어갔는지 확인 가능.
    """

    from app.services.rag.rag_service import RAGService
    rag = RAGService()
    col = rag.vector_store.collection

    # Chroma는 id 순서가 삽입 순서를 반영하므로 limit로 잘라서 역순 정렬 가능
    res = col.get(
        include=["metadatas", "documents"],
        limit=limit
    )

    ids = res.get("ids", [])
    metas = res.get("metadatas", [])
    docs = res.get("documents", [])

    # 가장 최근것이 뒤에 있을 가능성이 높으므로 뒤에서부터 50개 추출
    items = []
    for idx in range(len(ids) - 1, max(-1, len(ids) - 51), -1):
        meta = metas[idx]
        items.append({
            "idx": idx,
            "id": ids[idx],
            "external_doc_id": meta.get("external_doc_id"),
            "db_id": meta.get("db_id"),
            "paragraph_idx": meta.get("paragraph_idx"),
            "chunk_idx": meta.get("chunk_idx"),
            "preview": docs[idx][:80] if docs else None,
        })

    return {
        "count": len(items),
        "items": items
    }

@router.get("/debug/by-db/{doc_id}")
def debug_by_db_id(doc_id: int):
    rag = RAGService()
    col = rag.vector_store.collection

    result = col.get(
        where={"db_id": doc_id},
        include=["documents", "metadatas"],
        limit=10000
    )
    table_proc = TableProcessor(settings.EXTRACTED_DIR)

    items = []
    docs = result.get("documents", [])
    metas = result.get("metadatas", [])

    for i, meta in enumerate(metas):
        table_json = None

        # 표일 경우: 테이블 JSON 로드
        if meta.get("type") == "table":
            table_id = meta.get("table_id")
            filename = meta.get("filename") or meta.get("external_doc_id")

            if filename:
                doc_dir = f"extracted_{filename.replace('.hwpx', '')}"
                table_json = table_proc.get_table(doc_dir, table_id)

        items.append({
            "idx": i,
            "chunk_id": meta.get("chunk_id"),
            "paragraph_idx": meta.get("paragraph_idx"),
            "db_id": meta.get("db_id"),
            "external_doc_id": meta.get("external_doc_id"),
            "preview": docs[i][:80],
            "table": table_json,  # ← 표 JSON 포함!
        })

    return {
        "count": len(items),
        "items": items
    }

@router.get("/debug/by-external/{external_doc_id}")
def debug_by_external(external_doc_id: str, limit: int = 5000):
    """
    VectorDB에 저장된 metadata.external_doc_id 기준으로 조회.
    external_doc_id 매칭이 안 되는 문제 디버그용.
    """
    from app.services.rag.rag_service import RAGService
    rag = RAGService()
    col = rag.vector_store.collection

    # include를 명시해야 문서/메타데이터를 가져올 수 있음
    res = col.get(
        where={"external_doc_id": external_doc_id},
        include=["metadatas", "documents"],
        limit=limit
    )

    ids = res.get("ids",[])
    metas = res.get("metadatas") or []
    docs = res.get("documents") or []

    items = []
    for idx, meta in enumerate(metas):
        items.append({
            "idx": idx,
            "id": ids[idx],
            "doc_id": meta.get("db_id"),
            "external_doc_id": meta.get("external_doc_id"),
            "paragraph_idx": meta.get("paragraph_idx"),
            "chunk_idx": meta.get("chunk_idx"),
            "preview": (docs[idx][:100] if docs else None)
        })

    return {
        "query_external_doc_id": external_doc_id,
        "count": len(items),
        "items": items
    }

# app/api/v1/endpoints/rag_search.py
import pymysql
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.db import get_connection
from app.services.rag.rag_service import RAGService

router = APIRouter()
rag_service = RAGService()


class VectorSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5
    user_id: int


class VectorSearchHit(BaseModel):
    content: str
    score: float
    metadata: Dict[str, Any]


class VectorSearchResponse(BaseModel):
    query: str
    top_k: int
    hits: List[VectorSearchHit]

def _load_user_context(user_id: int):
    db = get_connection()
    cur = db.cursor(pymysql.cursors.DictCursor)

    # 사용자 정보/권한 조회
    sql = """
        SELECT 
            u.id,
            u.dept_id,
            u.project_id,
            u.role
        FROM users u
        WHERE u.id = %s
    """
    cur.execute(sql, (user_id,))
    row = cur.fetchone()

    if not row:
        return None

    return {
        "id": row["id"],
        "dept_id": row["dept_id"],
        "project_id": row["project_id"],
        "role": row["role"],
    }


@router.post(
    "/vector-search",
    response_model=VectorSearchResponse,
    summary="벡터 검색 (컨텍스트만 반환)",
    tags=["dev"],
)
def vector_search(payload: VectorSearchRequest):
    """
    - LLM 호출 없이, RAG 벡터검색 결과(청크 리스트)만 반환하는 API
    - 권한 필터링은 RAGService.query() 내부에서 수행
    """
    if not payload.query.strip():
        raise HTTPException(status_code=400, detail="query must not be empty")

    user = _load_user_context(payload.user_id)

    hits = rag_service.query(
        question=payload.query,
        top_k=payload.top_k,
        user=user,
    )

    # rag_service.query() 가 이미 {content, score, metadata} dict 리스트를 반환하므로 그대로 매핑
    return VectorSearchResponse(
        query=payload.query,
        top_k=payload.top_k or 5,
        hits=[VectorSearchHit(**h) for h in hits],
    )

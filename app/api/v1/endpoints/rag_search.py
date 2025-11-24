# app/api/v1/endpoints/rag_search.py

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


def _load_user_context(user_id: int) -> Dict[str, Any]:
    """
    RAGService._has_access 에서 사용하는 user 컨텍스트 생성.
    - 지금은 최소 정보만: id, dept_id, role
    - projects / collab_projects 는 TODO
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, dept_id, role FROM users WHERE id=%s",
            (user_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="User not found")

        # pymysql 기본 cursor → tuple
        user = {
            "id": row[0],
            "dept_id": row[1],
            "role": row[2],
            # TODO: 필요시 프로젝트/협업프로젝트 조회해서 채우기
            "projects": [],
            "collab_projects": [],
        }
        return user
    finally:
        cur.close()
        conn.close()


@router.post(
    "/vector-search",
    response_model=VectorSearchResponse,
    summary="벡터 검색 (컨텍스트만 반환)",
    tags=["rag"],
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

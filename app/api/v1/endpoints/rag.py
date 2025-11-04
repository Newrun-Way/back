from fastapi import APIRouter, Body, HTTPException, Request
from typing import Any, Dict
import asyncio


router = APIRouter()

@router.post("/query")
async def rag_query(request: Request, payload: Dict[str, Any] = Body(...)):
    """
    Request body: {"query": "질문 텍스트"} 또는 {"text": "..."}
    반환: {"result": ...}
    """
    query_text = payload.get("query") or payload.get("text")
    if not query_text:
        raise HTTPException(status_code=422, detail="missing 'query' or 'text' in body")

    pipeline = request.app.state.rag_pipeline

    # 파이프라인에 따른 메서드명 지원 (query, run 등)
    if hasattr(pipeline, "query"):
        res = pipeline.query(query_text)
    elif hasattr(pipeline, "run"):
        res = pipeline.run(query_text)
    else:
        raise HTTPException(status_code=500, detail="RAG pipeline has no callable 'query' or 'run'")

    # 동기/비동기 처리
    if asyncio.iscoroutine(res):
        res = await res

    return {"result": res}
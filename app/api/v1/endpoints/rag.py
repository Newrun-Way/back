# app/api/v1/endpoints/rag.py
from fastapi import APIRouter, Body, HTTPException
from typing import Any, Dict
from app.services.rag.pipeline import RAGPipeline

router = APIRouter(prefix="/rag")

@router.post("/query")
async def rag_query(payload: Dict[str, Any] = Body(...)):
    """
    Request body: {"query": "질문 텍스트"} 또는 {"text": "..."}
    반환: {"answer": str, "sources": [...], "context_used": str}
    """
    query_text = payload.get("query") or payload.get("text")
    if not query_text:
        raise HTTPException(status_code=422, detail="missing 'query' or 'text' in body")

    pipeline = RAGPipeline()
    return pipeline.query(query_text)

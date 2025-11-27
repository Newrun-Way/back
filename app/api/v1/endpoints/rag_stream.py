from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.services.rag.pipeline import RAGPipeline
import json
import asyncio

router = APIRouter(prefix="/sse", tags=["RAG-SSE"])

@router.get("/rag/stream")
async def rag_stream(query: str = Query(..., description="질문 텍스트")):
    """
    SSE 기반 스트리밍 RAG API
    Content-Type: text/event-stream
    """

    pipeline = RAGPipeline()

    # 1) 검색 (RAG)
    contexts = pipeline.retriever.query(query)
    context_str = "\n\n".join([c["content"] for c in contexts])

    async def event_generator():
        # 2) 스트리밍 답변 생성
        async for tok in pipeline.llm.generate_stream(context_str, query):
            yield f"data: {tok}\n\n"
            await asyncio.sleep(0)

        # 3) 출처(sources) 생성 (LLM 재호출 아님, generate_with_sources 사용)
        result = pipeline.llm.generate_with_sources(contexts, query)
        sources_json = json.dumps(result["sources"], ensure_ascii=False)

        yield f"event: sources\ndata: {sources_json}\n\n"
        yield f"event: end\ndata: END\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# app/api/v1/endpoints/chat.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from fastapi.responses import StreamingResponse
import asyncio

from app.services.chat.chat_service import ChatService

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    user_id: int  # 프론트엔드에서 로그인한 사용자

@router.post("/")
async def chat(req: ChatRequest):
    service = ChatService()
    try:
        answer = service.chat(
            conversation_id=req.conversation_id,
            message=req.message,
            user_id=req.user_id
        )
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream")
async def chat_stream(req: ChatRequest):
    service = ChatService()

    async def event_gen():
        async for tok in service.chat_stream(
            conversation_id=req.conversation_id,
            message=req.message,
            user_id=req.user_id
        ):
            yield f"data: {tok}\n\n"
            await asyncio.sleep(0)

        yield "event: end\ndata: END\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")
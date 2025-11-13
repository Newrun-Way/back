# app/api/v1/endpoints/chat.py

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.chat.chat_service import ChatService

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: str
    message: str


@router.post("/")
async def chat(req: ChatRequest):
    service = ChatService()
    answer = service.chat(
        conversation_id=req.conversation_id,
        message=req.message,
    )
    return {"answer": answer}

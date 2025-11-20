from fastapi import APIRouter, HTTPException
from app.services.chat.chat_session_service import ChatSessionService
from app.services.chat.chat_message_store import ChatMessageStore
from app.schemas.chat import ChatRoomDetail, ChatMessage, ChatSession
from app.services.chat.chat_service import ChatService
from pydantic import BaseModel

router = APIRouter(prefix="/chat/sessions", tags=["chat"])

session_service = ChatSessionService()
message_store = ChatMessageStore()

# 1. 채팅 세션 목록 조회
@router.get("/", response_model=list[ChatSession])
def list_sessions(user_id: int):
    return session_service.list_sessions(user_id)

# 2. 단일 세션 조회 (대화 기록 포함)
@router.get("/{session_id}", response_model=ChatRoomDetail)
def get_session(session_id: int):
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")

    messages = message_store.get_messages(str(session_id))

    return {
        "session": session,
        "messages": messages
    }

# 3. 채팅 세션 삭제 (DB soft delete + Chroma 메시지 삭제)
@router.delete("/{session_id}")
def delete_session(session_id: int):
    session = session_service.get_session(session_id)
    if not session:
        raise HTTPException(404, "session not found")

    # DB soft delete
    session_service.soft_delete(session_id)

    # Chroma 메시지 삭제
    message_store.delete_messages(str(session_id))

    return {"message": "session deleted"}

#4. 채팅 세션 생성
class SessionCreateRequest(BaseModel):
    user_id: int
    title: str | None = None


@router.post("/sessions")
def create_chat_session(req: SessionCreateRequest):
    """
    채팅 세션(대화방) 생성 API
    - DB에 session row 생성
    - Chroma memory(conversation_id) 초기화는 첫 메시지 때 자동 처리됨
    """
    session_id = session_service.create_session(req.user_id, req.title)

    # ChatMemory 는 mem.add_turn 시점에 자동 생성되므로 여기선 ID만 리턴하면 됨.
    return {
        "session_id": session_id,
        "user_id": req.user_id,
        "title": req.title,
    }
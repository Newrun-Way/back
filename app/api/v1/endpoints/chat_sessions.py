from fastapi import APIRouter, HTTPException
from app.services.chat_session_service import ChatSessionService
from app.services.chat_message_store import ChatMessageStore
from app.schemas.chat import ChatRoomDetail, ChatMessage, ChatSession

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

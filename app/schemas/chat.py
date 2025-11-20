from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatSession(BaseModel):
    id: int
    title: Optional[str]
    created_at: str
    updated_at: str

class ChatRoomDetail(BaseModel):
    session: ChatSession
    messages: List[ChatMessage]

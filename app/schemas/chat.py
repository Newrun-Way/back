from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatSession(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    is_deleted: int
    created_at: datetime
    updated_at: datetime

class ChatRoomDetail(BaseModel):
    session: ChatSession
    messages: List[ChatMessage]

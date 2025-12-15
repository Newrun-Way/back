from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class ChatMessage(BaseModel):
    role: str
    content: str
    created_at: Optional[str] = None
    doc_id: Optional[int] = None
    paragraph_idx: Optional[int] = None
    chunk_id: Optional[int] = None

class ChatSession(BaseModel):
    id: int
    user_id: int
    title: Optional[str]
    is_deleted: int
    refer_docs: Optional[List[int]] = None
    created_at: datetime
    updated_at: datetime

class ChatRoomDetail(BaseModel):
    session: ChatSession
    messages: List[ChatMessage]

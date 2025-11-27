# app/api/v1/endpoints/requests_dto.py
from pydantic import BaseModel
from typing import Optional

class RequestCreateDTO(BaseModel):
    requester_id: int
    project_id: int
    request_type: str   # CREATE / UPDATE / DELETE
    target_document_id: Optional[int] = None
    content: Optional[str] = None

class RejectDTO(BaseModel):
    reason: str

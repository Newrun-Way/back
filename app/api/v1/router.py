# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.parsing import router as parsing_router
from app.api.v1.endpoints.rag import router as rag_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.rag_admin import router as rag_admin_router
from app.api.v1.endpoints.chat_sessions import router as chat_sessions_router


api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(parsing_router, prefix="/parsing", tags=["parsing"])
api_router.include_router(rag_router, prefix="/rag", tags=["rag"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(documents_router)
api_router.include_router(rag_admin_router)
api_router.include_router(chat_sessions_router)

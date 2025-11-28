# app/api/v1/router.py
from fastapi import APIRouter

from app.api.v1.endpoints.health import router as health_router
from app.api.v1.endpoints.parsing import router as parsing_router
from app.api.v1.endpoints.rag import router as rag_router
from app.api.v1.endpoints.chat import router as chat_router
from app.api.v1.endpoints.documents import router as documents_router
from app.api.v1.endpoints.rag_admin import router as rag_admin_router
from app.api.v1.endpoints.chat_sessions import router as chat_sessions_router
from app.api.v1.endpoints.admin.dept import router as dept_router
from app.api.v1.endpoints.admin.project import router as project_router
from app.api.v1.endpoints.admin.project_permissions import router as project_permission_router
from app.api.v1.endpoints.rag_search import router as rag_search_router
from app.api.v1.endpoints.admin.admin_doc import router as admin_doc_router
from app.api.v1.endpoints.requests import router as requests_router
from app.api.v1.endpoints.admin.admin_requests import router as admin_request_router

# from app.api.v1.endpoints.rag_stream import router as rag_stream_router

api_router = APIRouter()

api_router.include_router(health_router, prefix="/health", tags=["health"])

api_router.include_router(parsing_router, prefix="/parsing", tags=["upload"])
api_router.include_router(rag_router, tags=["rag"])
api_router.include_router(rag_search_router, tags=["vector_search"])

api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(documents_router)
api_router.include_router(rag_admin_router)
api_router.include_router(chat_sessions_router)

api_router.include_router(dept_router)
api_router.include_router(project_router)
api_router.include_router(project_permission_router, prefix="/admin")
api_router.include_router(admin_doc_router, prefix="/admin")

api_router.include_router(requests_router)
api_router.include_router(admin_request_router, prefix="/admin")
# api_router.include_router(rag_stream_router)
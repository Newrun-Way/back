# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import rag as rag_ep
from app.api.v1.endpoints import health as health_ep
from app.api.v1.endpoints import parsing as parsing_ep  # 이미 있는 업로드/파싱 API

router = APIRouter()
router.include_router(health_ep.router)  # /health
router.include_router(rag_ep.router)       # /rag/...
router.include_router(parsing_ep.router)   # /upload-and-parse 등

from fastapi import APIRouter
from .endpoints import health, parsing
from .endpoints import rag as rag_endpoint


router = APIRouter()
router.include_router(health.router, prefix="", tags=["health"])
router.include_router(parsing.router, prefix="/parsing", tags=["parsing"])

router.include_router(rag_endpoint.router, prefix="/rag", tags=["rag"])

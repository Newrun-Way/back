from fastapi import APIRouter
from .endpoints import health, parsing


router = APIRouter()
router.include_router(health.router, prefix="/health", tags=["health"])
router.include_router(parsing.router, prefix="/parsing", tags=["parsing"])
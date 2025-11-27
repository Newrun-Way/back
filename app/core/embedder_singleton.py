#app/core/embedder_singleton.py

from app.services.rag.embedder import DocumentEmbedder
from app.core.config import get_settings

settings = get_settings()

# 전역 싱글톤 (앱 시작 시 1회 로딩)
GLOBAL_EMBEDDER = DocumentEmbedder(
    model_name=settings.EMBEDDING_MODEL,
    device=settings.EMBEDDING_DEVICE,
)
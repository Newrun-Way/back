import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router as v1_router
from app.services.rag.pipeline import RAGPipeline
import os

settings = get_settings()
setup_logging(settings.LOG_LEVEL)

app = FastAPI(title=settings.APP_NAME, version="1.0.1")

# RAG 파이프라인 인스턴스를 app의 state에 저장
# @app.on_event("startup")
# async def startup_event():
#     # 필요한 디렉토리 생성
#     os.makedirs(settings.VECTOR_STORE_DIR, exist_ok=True)
#     os.makedirs(settings.EXTRACTED_DIR, exist_ok=True)

#     pipeline = RAGPipeline()
#     # pipeline = RAGPipeline(settings=settings)
#     app.state.rag_pipeline = pipeline
#     print(f"RAG Pipeline initialized. Vector store at: {settings.VECTOR_STORE_DIR}")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.APP_PORT, reload=True)

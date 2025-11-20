from pydantic_settings import BaseSettings
from functools import lru_cache
from pathlib import Path

# BASE_DIR = Path(__file__).resolve().parents[2]  # <repo>/back
# APP_DIR  = BASE_DIR / "app"

class Settings(BaseSettings):
    APP_NAME: str = "Newrun-Back"
    APP_ENV: str = "dev"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    HWPLIB_JAR: str | None = None

    #MySQL 연결
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "alain_db"

    # RAG 설정
    DATA_DIR: str = "data"
    VECTOR_STORE_DIR: str = "app/data/vector_store"
    VECTOR_STORE_INDEX_TYPE: str = "flat"
    # 샤딩 사용 여부 (False면 단일 인덱스)
    SHARDING_ENABLED: bool = True
    
    UPLOAD_DIR: str = "app/data/uploads"
    EXTRACTED_DIR: str = "extracted_results"

    OPENAI_API_KEY: str = ""

    EMBEDDING_DEVICE: str = "cuda"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIM: int = 1024
    MAX_SEQ_LENGTH: int = 8192

    LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1024

    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    SEPARATORS: list[str] = ["\n\n", "\n", ".", "!", "?", " ", ""]

    TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.7

    SYSTEM_PROMPT: str = """당신은 한국어 공문서 전문 AI 어시스턴트입니다.

역할:
- 제공된 문서를 정확히 읽고 질문에 답변
- 문서에 없는 내용은 "문서에서 찾을 수 없습니다"라고 명확히 표시
- 표의 내용은 정확히 인용

답변 형식:
1. 핵심 답변 (1-2문장)
2. 근거 (문서 인용)
3. 출처 (문서 이름)

규칙:
- 존댓말 사용
- 간결하고 명확하게
- 추측하지 말 것
- 표는 마크다운 형식으로 표시
"""
    USER_PROMPT_TEMPLATE: str = """다음 문서를 참고하여 질문에 답해주세요.

[문서 내용]
{context}

[질문]
{question}

[지시사항]
- 문서에 명시된 내용만 사용
- 표가 있다면 정확히 인용
- 출처 문서명 반드시 명시
"""


class Config:
    env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
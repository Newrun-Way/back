from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
APP_NAME: str = "Newrun-Back"
APP_ENV: str = "dev"
APP_PORT: int = 8000
LOG_LEVEL: str = "INFO"
HWPLIB_JAR: str | None = None
OUTPUT_ROOT: str = "/data/extracted_results"


class Config:
env_file = ".env"


@lru_cache
def get_settings() -> Settings:
return Settings()
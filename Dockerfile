# ===========================================================
# Base Image (공통: FastAPI + Worker)
# ===========================================================
FROM python:3.11-slim-bookworm AS base

WORKDIR /app

# --- system packages ---
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jdk \
        curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Java env ---
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${PATH}:${JAVA_HOME}/bin"

# --- Install project dependencies ---
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Copy application code ---
COPY ./app /app/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app


# ===========================================================
# API Server
# ===========================================================
FROM base AS api
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# ===========================================================
# Worker (CPU)
# ===========================================================
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04 AS worker

ENV EMBEDDING_DEVICE=cuda
ENV USE_RERANKER=false
ENV PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True

CMD ["celery", "-A", "app.core.celery_app.celery_app", "worker", "-l", "info", "--concurrency=1"]


# ===========================================================
# Flower (독립 전용 이미지)
# ===========================================================
FROM python:3.11-slim-bookworm AS flower

WORKDIR /app

# 1. 라이브러리 설치
# - celery, flower, redis: Flower 구동 필수
# - pydantic-settings: config.py(Settings 클래스) 로드용 필수
RUN pip install --no-cache-dir \
      celery \
      flower \
      redis \
      pydantic-settings \
      pymysql

# 2. 소스 코드 복사
# - Celery가 설정을 읽을 때 app/core/celery_app.py -> config.py 순으로 참조하므로 코드가 필요합니다.
COPY ./app /app/app

# 3. 환경 변수 설정
# - /app 경로를 파이썬 라이브러리 경로에 포함시켜 'app.core...' 모듈을 찾게 합니다.
ENV PYTHONPATH=/app

EXPOSE 5555

CMD ["celery", "flower", "--port=5555"]


# ===========================================================
# Default
# ===========================================================
FROM api AS default

# ===========================================================
# Base Image (공통 레이어)
# FastAPI + JPype + Java 17 + Python 3.11
# ===========================================================
FROM python:3.11-slim-bookworm AS base

# 작업 디렉토리
WORKDIR /app

# -----------------------------------------------------------
# 필수 시스템 패키지 및 Java 설치
# -----------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        openjdk-17-jdk \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# JAVA 환경변수
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${PATH}:${JAVA_HOME}/bin"

# -----------------------------------------------------------
# Python 의존성 설치
# -----------------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./app /app/app

# -----------------------------------------------------------
# 공통 환경변수
# -----------------------------------------------------------
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# ===========================================================
# Stage 1 - API 서버 (FastAPI)
# ===========================================================
FROM base AS api
EXPOSE 8000

# FastAPI 실행
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# GPU 사용 시 compose.yml의 gpus 설정으로 제어


# ===========================================================
# Stage 2 - Celery Worker (CPU)
# ===========================================================
FROM base AS worker

# Worker는 GPU가 필요 없으므로 CPU로만 실행
ENV EMBEDDING_DEVICE=cpu

# Celery Worker 실행 (네 back 레포 기준)
CMD ["celery", "-A", "app.core.celery_app.celery_app", "worker", "-l", "info"]


# ===========================================================
# Stage 3 - Flower 모니터링
# ===========================================================
FROM base AS flower
EXPOSE 5555

CMD ["celery", "-A", "app.core.celery_app.celery_app", "flower", "--port=5555"]


# ===========================================================
# Stage 4 - Default (optional)
# ===========================================================
FROM api AS default

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
FROM base AS worker
ENV EMBEDDING_DEVICE=cpu
CMD ["celery", "-A", "app.core.celery_app.celery_app", "worker", "-l", "info"]


# ===========================================================
# Flower (독립 전용 이미지)
# ===========================================================
FROM python:3.11-slim-bookworm AS flower

# Flower ONLY needs Celery + Flower + Redis client
RUN pip install --no-cache-dir \
      celery \
      flower \
      redis

WORKDIR /app
EXPOSE 5555

CMD ["celery", "flower", "--port=5555"]


# ===========================================================
# Default
# ===========================================================
FROM api AS default

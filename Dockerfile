# ===========================================================
# OWPML Back - FastAPI + JPype + Java (OpenJDK 17)
# ===========================================================
FROM python:3.11-slim-bookworm
# 작업 디렉토리 설정
WORKDIR /app

# -----------------------------------------------------------
# 필수 시스템 패키지 및 Java 설치
# -----------------------------------------------------------
RUN apt-get update && \
    apt-get install -y openjdk-17-jdk && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# JAVA_HOME 설정 (Linux 기준)
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${PATH}:${JAVA_HOME}/bin"

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY ./app /app/app

# FastAPI 실행 설정
EXPOSE 8000

# 개발용 (자동 리로드) 실행 명령
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

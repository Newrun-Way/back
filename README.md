# OWPML RAG 프로젝트를 위한 FastAPI 백엔드

이 프로젝트는 OWPML1 리포지토리의 파싱 기능을 통합하여 HWP 및 HWPX 문서를 파싱하기 위한 FastAPI 백엔드를 제공합니다.

## 로컬에서 설정 및 실행 (Docker 제외)

로컬 컴퓨터에서 직접 FastAPI 애플리케-이션을 실행하려면 다음 단계를 따르세요.

1.  **`back` 디렉토리로 이동:**
    ```bash
    cd C:\한컴개발\파이썬\back
    ```

2.  **Python 종속성 설치:**
    pip를 사용하여 필요한 Python 패키지를 설치합니다.
    ```bash
    pip install -r requirements.txt
    ```

3.  **JDK(Java Development Kit) 설치 및 `JAVA_HOME` 설정:**
    HWP 파일 파싱에는 시스템에 JDK가 설치되어 있어야 합니다. `JAVA_HOME` 환경 변수가 JDK 설치 경로로 설정되어 있는지 확인하세요. 그렇지 않은 경우 JDK를 다운로드하여 설치하고(예: [Adoptium](https://adoptium.net/)) `JAVA_HOME`을 구성하세요.

4.  **`hwplib-1.1.8.jar` 복사:**
    HWP 파싱에 필수적인 `hwplib-1.1.8.jar` 파일을 `OWPML1` 프로젝트에서 `back/app/python-hwplib/` 디렉토리로 복사해야 합니다. 수동으로 수행하거나 다음 명령을 사용할 수 있습니다.
    ```bash
    copy "C:\한컴개발\파이썬\OWPML1\python-hwplib\hwplib-1.1.8.jar" "C:\한컴개발\파이썬\back\app\python-hwplib\"
    ```

5.  **FastAPI 애플리케이션 실행:**
    모든 종속성이 설치되고 JAR 파일이 제자리에 있으면 Uvicorn을 사용하여 FastAPI 애플리케이션을 시작합니다.
    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    ```
    API는 `http://localhost:8000`에서 액세스할 수 있습니다.

## Docker로 설정 및 실행

Docker를 사용하여 FastAPI 애플리케이션을 실행하려면 다음 단계를 따르세요.

1.  **`back` 디렉토리로 이동:**
    ```bash
    cd C:\한컴개발\파이썬\back
    ```

2.  **Docker 이미지 빌드:**
    ```bash
    docker build -t owpml-fastapi-backend .
    ```
    이 명령은 `owpml-fastapi-backend`라는 Docker 이미지를 빌드합니다. 이 프로세스에는 JDK 및 Python 종속성 설치가 포함되며 시간이 걸릴 수 있습니다.

3.  **Docker 컨테이너 실행:**
    ```bash
    docker run -d --name owpml-parser -p 8000:8000 owpml-fastapi-backend
    ```
    이렇게 하면 컨테이너가 백그라운드에서 시작되고 호스트의 8000번 포트가 컨테이너의 8000번 포트에 매핑됩니다.

## API 엔드포인트

애플리케이션이 실행되면(로컬 또는 Docker를 통해) 다음에서 API에 액세스할 수 있습니다.

-   **Swagger UI:** `http://localhost:8000/docs`
-   **파일 업로드 및 파싱 엔드포인트:** `http://localhost:8000/api/v1/parsing/upload-and-parse/`
    -   이 엔드포인트는 `.hwp` 및 `.hwpx` 파일 업로드를 허용합니다.

## 프로젝트 구조

```
back/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   ├── __init__.py
│   │       │   └── parsing.py
│   │       ├── __init__.py
│   │       └── router.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── jpype_setup.py
│   │   ├── logging.py
│   │   └── parser.py
│   ├── main.py
│   └── python-hwplib/  # HWP 파싱을 위한 hwplib-1.1.8.jar 포함
├── Dockerfile
├── requirements.txt
└── README.md
```
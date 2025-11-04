# 🧱 알랭 Backend (FastAPI + JPype + Docker)

> **OWPML 필터 기반 문서 질의응답 서비스 `알랭` 백엔드**
>
> 이 프로젝트는 모든 개발과 실행 환경을 **Docker 기반으로 통일**합니다.  
> 로컬 Python 실행은 금지하며, FastAPI + Java(JPype) 환경은 **컨테이너 내부에서만** 작동합니다.

---

## ⚙️ 환경 개요

| 구성 요소 | 버전 / 설명 |
|------------|--------------|
| OS | Ubuntu (Docker 내부) |
| Python | 3.11 |
| Java | OpenJDK 17 |
| Framework | FastAPI + Uvicorn |
| Container Tool | Docker Compose |
| 주요 패키지 | JPype1, pydantic-settings, python-multipart |

---

## 📁 프로젝트 구조
```markdown
back/
├── app/
│ ├── main.py # FastAPI 진입점
│ ├── modules/
│ │ ├── jpype_setup.py # JPype + JAVA_HOME 자동 설정
│ │ └── init.py
│ ├── routes/
│ │ └── extract_route.py # 문서 추출 API 엔드포인트 (예시)
│ ├── services/
│ │ └── extract_service.py # 비즈니스 로직 계층
│ ├── models/
│ │ └── request_schema.py # Pydantic 기반 요청/응답 모델
│ └── init.py
│
├── requirements.txt # Python 의존성 목록
├── Dockerfile # FastAPI + JPype + Java 환경 빌드 설정
├── docker-compose.yml # 컨테이너 실행/연동 설정
├── Makefile # (선택) 명령어 단축용
└── README.md # 프로젝트 문서
```
app/ 폴더는 FastAPI 애플리케이션의 루트이며,
routes, services, models, modules 로 기능이 분리됩니다.
Dockerfile / docker-compose.yml 은 실행환경 통일을 위한 필수 구성요소입니다.

---
## 🚀 실행 가이드 (Docker 전용)

### 1️⃣ 최초 빌드 (이미지 생성)

```bash
docker compose build --no-cache
```
- Dockerfile 기반으로 Python + Java 환경 이미지 생성

- `--no-cache` 옵션은 캐시를 무시하고 완전 새로 빌드할 때 사용
(의존성 추가나 Dockerfile 수정 시만 필요)

2️⃣ 개발 서버 실행
```bash
docker compose up
```
- FastAPI 서버가 실행되며 로그가 터미널에 출력됩니다.


- 브라우저에서 접속:
👉 http://localhost:8000/docs



💡 백그라운드로 실행하려면:
docker compose up -d


---

### 3️⃣ 서버 중지 / 정리

```bash
docker compose down
```
💡 완전 초기화(볼륨 포함):
```bash
docker compose down -v
```
### 4️⃣ 로그 확인 ```bash docker compose logs -f ```
- `-f` 옵션으로 실시간 로그 스트리밍
- `Ctrl + C` 로 종료
---


### 5️⃣ 컨테이너 내부 접속 (디버깅용)
```bash docker exec -it owpml_backend bash ``
> 내부에서 Java 환경 확인:
```bash
> echo $JAVA_HOME 
java -version 
```
---


## 🧠 주요 명령 요약

| 목적 | 명령어 |
|------|--------|
| 컨테이너 빌드 | `docker compose build` |
| 캐시 무시 재빌드 | `docker compose build --no-cache` |
| 서버 실행 (로그 표시) | `docker compose up` |
| 서버 실행 (백그라운드) | `docker compose up -d` |
| 서버 중지 | `docker compose down` |
| 볼륨 포함 종료 | `docker compose down -v` |
| 로그 보기 | `docker compose logs -f` |
| 컨테이너 셸 접속 | `docker exec -it owpml_backend bash` |
---

## 🧩 Java / JPype 환경 확인

JPype가 올바르게 Java를 인식하는지 테스트하려면:

```bash
docker exec -it owpml_backend bash
python -c "from app.modules.jpype_setup import get_java_info; print(get_java_info())"
```
정상 출력 예시:
```json
{
  "java_home": "/usr/lib/jvm/java-17-openjdk-amd64",
  "java_version": "openjdk version \"17.0.17\" 2025-10-21",
  "java_path": "/usr/bin/java"
}
```


## 🧰 개발 플로우 요약

| 단계 | 설명 |
|------|------|
| 1️⃣ 코드 수정 | 로컬 IDE(VSCode, WebStorm 등)에서 편집 |
| 2️⃣ 자동 반영 | `docker-compose.yml`의 `volumes` 설정에 따라 컨테이너 실시간 반영 |
| 3️⃣ 테스트 | [http://localhost:8000/docs](http://localhost:8000/docs) 에서 확인 |
| 4️⃣ 빌드 필요 시 | `docker compose build --no-cache` 실행 |

---

## ⚠️ 운영 정책

- 로컬 Python 가상환경(`venv`) 사용 **금지**
- 모든 패키지 의존성은 `requirements.txt`에 명시
- **JAVA_HOME**은 `/usr/lib/jvm/java-17-openjdk-amd64`로 고정
- 팀 전체가 **Docker Desktop (또는 WSL2)** 환경에서 개발

---

## ❓ 자주 묻는 질문 (FAQ)

### Q1. 코드 수정했는데 반영이 안 돼요.
> A. `docker-compose.yml`의 `volumes` 설정을 확인하세요.  
> 예시:
> ```yaml
> volumes:
>   - ./app:/app/app
> ```

---

### Q2. `JAVA_HOME` 관련 오류가 납니다.
> A. 컨테이너 내부에서 다음 명령으로 확인하세요:
> ```bash
> echo $JAVA_HOME
> ls $JAVA_HOME/lib/server/libjvm.so
> ```
> 파일이 없으면 Dockerfile의 JDK 설치 부분을 확인하세요:
> ```dockerfile
> RUN apt-get update && apt-get install -y openjdk-17-jdk
> ```

---

### Q3. 로컬에서 `python main.py`로 실행해도 되나요?
> ❌ 아니요.  
> 이 프로젝트는 **Docker 환경 전용**입니다.  
> 로컬에서 실행 시 Java 연결(JPype)이 실패할 수 있습니다.

---

## 🔁 전체 플로우 요약

| 단계 | 명령 | 설명 |
|------|------|------|
| ① | `docker compose build` | 초기 빌드 |
| ② | `docker compose up` | 서버 실행 |
| ③ | `docker exec -it owpml_backend bash` | 내부 셸 접속 |
| ④ | `docker compose down` | 종료 및 정리 |

---

## 🧩 선택사항: Makefile 단축 명령 (선택)

원한다면 다음 `Makefile`을 루트에 추가하여 명령을 단축할 수 있습니다:

```makefile
.PHONY: up up-d down build logs bash

up:
	docker compose up

up-d:
	docker compose up -d

build:
	docker compose build --no-cache

down:
	docker compose down

logs:
	docker compose logs -f

bash:
	docker exec -it owpml_backend bash
```

이후 다음 명령으로 동일하게 사용 가능합니다:

```bash
make up      # == docker compose up
make down    # == docker compose down
make logs    # == docker compose logs -f
```

---

## 👥 팀원용 온보딩 요약

1️⃣ 저장소 클론
```bash
git clone <repo-url>
cd back
```

2️⃣ Docker 빌드
```bash
docker compose build
```

3️⃣ 서버 실행
```bash
docker compose up
```

4️⃣ 브라우저에서 확인  
👉 [http://localhost:8000/docs](http://localhost:8000/docs)

---

> 💬 **Tip:**  
> 모든 명령은 Docker 기반으로 실행되어,  
> macOS / Windows / Linux 모두 **환경 차이 없이 동일하게 작동**합니다.

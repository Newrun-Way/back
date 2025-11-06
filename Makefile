# ===============================
# Make targets for Docker Compose
# ===============================
# 기본 프로파일은 cpu, 필요 시 gpu로 오버라이드
# WSL/Unix/macOS에서 그대로 사용 가능
# Windows PowerShell도 WSL 터미널이면 동일 사용 가능

# 공통 옵션
COMPOSE := docker compose
# 필요하다면 파일 명시 (기본 docker-compose.yml이면 주석 유지)
# COMPOSE := docker compose -f docker-compose.yml

.PHONY: dev gpu up up-d down down-v logs ps rebuild bash config clean prune

## 로컬 개발(CPU) - 포그라운드
dev:
	COMPOSE_PROFILES=cpu $(COMPOSE) up

## 배포(GPU) - 포그라운드
gpu:
	COMPOSE_PROFILES=gpu $(COMPOSE) up

## 공통: 백그라운드 실행
up-d:
	COMPOSE_PROFILES=$${COMPOSE_PROFILES:-cpu} $(COMPOSE) up -d

## 종료
down:
	$(COMPOSE) down

## 종료 + 볼륨정리(개발 캐시까지 리셋)
down-v:
	$(COMPOSE) down -v

## 로그 팔로우
logs:
	$(COMPOSE) logs -f

## 프로세스 상태
ps:
	$(COMPOSE) ps

## 강제 재빌드(캐시무시)
rebuild:
	$(COMPOSE) build --no-cache

## 컨테이너 쉘 접속 (기본 CPU 컨테이너명 기준)
bash:
	docker exec -it owpml_backend bash

## Compose가 최종적으로 인식한 설정 보기
config:
	$(COMPOSE) config

## 불필요 이미지/빌드캐시 정리(주의)
clean:
	docker system prune -f

## 진짜 전체 정리(더 주의)
prune:
	docker system prune -a --volumes -f

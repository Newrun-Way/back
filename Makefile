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

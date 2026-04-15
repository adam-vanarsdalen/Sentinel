SHELL := /bin/bash

.PHONY: up down restart logs ps backend-logs frontend-logs worker-logs test smoke validate bootstrap-admin

up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose down
	docker compose up --build -d

logs:
	docker compose logs -f

ps:
	docker compose ps

backend-logs:
	docker compose logs -f backend

frontend-logs:
	docker compose logs -f frontend

worker-logs:
	docker compose logs -f worker

test:
	docker compose run --rm --no-deps backend pytest -q
	docker compose run --rm --no-deps frontend npm run lint

smoke:
	./scripts/smoke-test.sh

validate:
	./scripts/validate_release.sh

bootstrap-admin:
	./scripts/bootstrap-admin.sh

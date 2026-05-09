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
	docker compose build backend
	docker compose run --rm --no-deps -v "$$(pwd)/backend/tests:/app/tests:ro" backend pytest -q
	docker run --rm \
		--user "$$(id -u):$$(id -g)" \
		-e HOME=/tmp/node-home \
		-e npm_config_cache=/tmp/node-home/npm-cache \
		-v "$$(pwd)/frontend:/app" \
		-w /app \
		node:20-alpine \
		sh -lc "npm ci && npm run lint"

smoke:
	./scripts/smoke-test.sh

validate:
	./scripts/validate_release.sh

bootstrap-admin:
	./scripts/bootstrap-admin.sh

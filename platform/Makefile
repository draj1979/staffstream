.PHONY: up down logs lint test migrate run-tenant-service run-employee-service

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

lint:
	uv run ruff check .

test:
	uv run pytest

migrate:
	cd services/tenant-service && uv run alembic upgrade head
	cd services/employee-service && uv run alembic upgrade head

run-tenant-service:
	uv run uvicorn tenant_service.main:app --reload --port 8001 --app-dir services/tenant-service/src

run-employee-service:
	uv run uvicorn employee_service.main:app --reload --port 8002 --app-dir services/employee-service/src

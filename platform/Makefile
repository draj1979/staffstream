.PHONY: up down logs lint test migrate \
	run-tenant-service run-employee-service run-auth-service run-agent-registry run-llm-gateway \
	run-openclaw-runtime run-memory-service

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
	cd services/auth-service && uv run alembic upgrade head
	cd services/agent-registry && uv run alembic upgrade head
	cd services/memory-service && uv run alembic upgrade head

run-tenant-service:
	uv run uvicorn tenant_service.main:app --reload --port 8001 --app-dir services/tenant-service/src

run-employee-service:
	uv run uvicorn employee_service.main:app --reload --port 8002 --app-dir services/employee-service/src

run-auth-service:
	uv run uvicorn auth_service.main:app --reload --port 8003 --app-dir services/auth-service/src

run-agent-registry:
	uv run uvicorn agent_registry.main:app --reload --port 8004 --app-dir services/agent-registry/src

run-llm-gateway:
	uv run uvicorn llm_gateway.main:app --reload --port 8005 --app-dir services/llm-gateway/src

run-openclaw-runtime:
	uv run uvicorn openclaw_runtime.main:app --reload --port 8006 --app-dir services/openclaw-runtime/src

run-memory-service:
	uv run uvicorn memory_service.main:app --reload --port 8007 --app-dir services/memory-service/src

.PHONY: up down logs lint test migrate \
	run-tenant-service run-employee-service run-auth-service run-agent-registry run-llm-gateway \
	run-openclaw-runtime run-memory-service run-knowledge-service run-api-gateway run-analytics-service \
	run-skill-marketplace run-audit-service \
	docker-build docker-build-tenant-service docker-build-employee-service docker-build-auth-service \
	docker-build-agent-registry docker-build-llm-gateway docker-build-openclaw-runtime \
	docker-build-memory-service docker-build-knowledge-service docker-build-api-gateway \
	docker-build-analytics-service docker-build-skill-marketplace docker-build-audit-service

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
	cd services/knowledge-service && uv run alembic upgrade head
	cd services/analytics-service && uv run alembic upgrade head
	cd services/skill-marketplace && uv run alembic upgrade head
	cd services/audit-service && uv run alembic upgrade head

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

run-knowledge-service:
	uv run uvicorn knowledge_service.main:app --reload --port 8008 --app-dir services/knowledge-service/src

run-api-gateway:
	uv run uvicorn api_gateway.main:app --reload --port 8000 --app-dir services/api-gateway/src

run-analytics-service:
	uv run uvicorn analytics_service.main:app --reload --port 8009 --app-dir services/analytics-service/src

run-skill-marketplace:
	uv run uvicorn skill_marketplace.main:app --reload --port 8010 --app-dir services/skill-marketplace/src

run-audit-service:
	uv run uvicorn audit_service.main:app --reload --port 8011 --app-dir services/audit-service/src

# Each image is built from the repo root (uv workspace — every service
# depends on sibling libs/ packages), one Dockerfile per service.
docker-build: docker-build-tenant-service docker-build-employee-service docker-build-auth-service \
	docker-build-agent-registry docker-build-llm-gateway docker-build-openclaw-runtime \
	docker-build-memory-service docker-build-knowledge-service docker-build-api-gateway \
	docker-build-analytics-service docker-build-skill-marketplace docker-build-audit-service

docker-build-tenant-service:
	docker build -f services/tenant-service/Dockerfile -t staffstream/tenant-service:latest .

docker-build-employee-service:
	docker build -f services/employee-service/Dockerfile -t staffstream/employee-service:latest .

docker-build-auth-service:
	docker build -f services/auth-service/Dockerfile -t staffstream/auth-service:latest .

docker-build-agent-registry:
	docker build -f services/agent-registry/Dockerfile -t staffstream/agent-registry:latest .

docker-build-llm-gateway:
	docker build -f services/llm-gateway/Dockerfile -t staffstream/llm-gateway:latest .

docker-build-openclaw-runtime:
	docker build -f services/openclaw-runtime/Dockerfile -t staffstream/openclaw-runtime:latest .

docker-build-memory-service:
	docker build -f services/memory-service/Dockerfile -t staffstream/memory-service:latest .

docker-build-knowledge-service:
	docker build -f services/knowledge-service/Dockerfile -t staffstream/knowledge-service:latest .

docker-build-api-gateway:
	docker build -f services/api-gateway/Dockerfile -t staffstream/api-gateway:latest .

docker-build-analytics-service:
	docker build -f services/analytics-service/Dockerfile -t staffstream/analytics-service:latest .

docker-build-skill-marketplace:
	docker build -f services/skill-marketplace/Dockerfile -t staffstream/skill-marketplace:latest .

docker-build-audit-service:
	docker build -f services/audit-service/Dockerfile -t staffstream/audit-service:latest .

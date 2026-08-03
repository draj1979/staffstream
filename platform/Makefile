.PHONY: up down logs lint test

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

.PHONY: install dev test lint typecheck migrate up down

install:
	uv sync

dev:
	uvicorn app.main:app --reload

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy app

migrate:
	uv run alembic upgrade head

up:
	docker compose up --build

down:
	docker compose down -v

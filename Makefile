.PHONY: install format lint audit test test-integration test-all up down logs

install:
	uv sync

format:
	uv run ruff format .
	uv run ruff check --fix .

lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy

audit:
	uv audit --preview-features audit-command

test:
	uv run pytest --cov --cov-report=term-missing

test-integration:
	uv run pytest -m integration

test-all:
	uv run pytest -m "integration or not integration" --cov --cov-report=term-missing

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs --follow api worker beat

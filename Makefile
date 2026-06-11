.PHONY: dev migrate migration seed test install

install:
	uv sync --all-groups

dev:
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

migration:
	uv run alembic revision --autogenerate -m "initial"

seed:
	uv run python seed.py

test:
	uv run pytest tests/ -v

sync:
	uv run python sync_results.py

# GOODYEXCELLENT COUTURE — API

FastAPI + PostgreSQL backend. Requirements live in `../DOCS/SRS — GOODYEXCELLENT COUTURE Website.md`; progress is tracked in `../DOCS/BACKEND-CHECKLIST.md`.

## Setup

```bash
cp .env.example .env
docker compose up -d db          # local PostgreSQL
uv sync
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Commands

| Task | Command |
| --- | --- |
| Run API | `uv run uvicorn app.main:app --reload` |
| Tests | `uv run pytest` |
| Lint / format | `uv run ruff check .` / `uv run ruff format .` |
| New migration | `uv run alembic revision --autogenerate -m "message"` |
| Apply migrations | `uv run alembic upgrade head` |

## Layout

```
app/
  main.py        FastAPI app, CORS, rate limiting
  core/          config, security (Argon2 + JWT), limiter
  db/            declarative base, async session
  models/        SQLAlchemy models (SRS 6.1 entities)
  schemas/       Pydantic request/response models
  api/v1/        routers, one per feature group
  services/      email, image processing
alembic/         migrations
tests/
```

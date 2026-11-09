# GOODYEXCELLENT COUTURE — API

The backend for the GOODYEXCELLENT COUTURE website: a public read API (services, gallery, testimonials, site
settings), four enquiry forms, and an admin API for the owner and staff.

Built with FastAPI, SQLAlchemy 2 (async), PostgreSQL 17 and Alembic.

- Requirements: `../DOCS/SRS — GOODYEXCELLENT COUTURE Website.md`
- Progress: `../DOCS/BACKEND-CHECKLIST.md`
- Security review and deployment checklist: `../DOCS/SECURITY-REVIEW.md`
- Build log: `../DOCS/log.md`

## Requirements

- Python 3.13 and [uv](https://docs.astral.sh/uv/)
- PostgreSQL 17. The easiest way is Docker (`docker-compose.yml` is included). Without Docker, install PostgreSQL 17
  and create a user, password and database all named `goody`.

## Quick start

Run these from the `backend/` folder.

```bash
uv sync                          # install dependencies
cp .env.example .env             # then edit .env (see below)
docker compose up -d db          # start PostgreSQL
uv run alembic upgrade head      # create the tables
OWNER_EMAIL=you@example.com OWNER_PASSWORD='a-long-password-12+' uv run python -m app.db.seed
uv run fastapi dev               # start the API on http://localhost:8000
```

On PowerShell, set the seed variables first: `$env:OWNER_EMAIL="you@example.com"; $env:OWNER_PASSWORD="..."`.

At the least, set `JWT_SECRET` in `.env` to 32 or more random characters. Admin sign-in is off without it:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

The seed creates the Owner account (password: at least 12 characters), the 8 services and the site contact details.
It is safe to run again. **Remove `OWNER_PASSWORD` afterwards.**

Interactive API docs are at <http://localhost:8000/docs> in development only. They are switched off when
`ENVIRONMENT=production`.

## Configuration

All settings come from environment variables or `.env`. `.env.example` lists every one with its default.

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT` | `development` or `production`. Production turns off the docs and schema and turns on HSTS. |
| `DATABASE_URL` | `postgresql+asyncpg://user:password@host:5432/dbname` |
| `JWT_SECRET` | 32+ random characters. Rotating it signs every admin out. |
| `ACCESS_TOKEN_MINUTES`, `LOGIN_MAX_FAILURES`, `LOGIN_LOCK_MINUTES` | Admin session length and account lockout. |
| `PASSWORD_RESET_MINUTES`, `FRONTEND_URL` | Password-reset expiry; reset links are built from `FRONTEND_URL`. |
| `CORS_ORIGINS` | JSON list of allowed website origins, e.g. `["https://example.com"]`. |
| `RATE_LIMIT_MAX_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS` | Limit on enquiry-form submissions per address. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `MAIL_FROM`, `ENQUIRY_NOTIFY_TO` | Email. Leave `SMTP_HOST` empty to disable sending. |
| `UPLOAD_DIR`, `API_PUBLIC_URL`, `MAX_UPLOAD_BYTES` | Image storage, the public address used to build image links, and the size cap. |
| `OWNER_EMAIL`, `OWNER_PASSWORD` | Used only by the seed command. |

## Endpoints

**Public**

| Route | What it does |
| --- | --- |
| `GET /health`, `GET /health/db` | Liveness and database checks |
| `GET /services`, `GET /services/{slug}` | Service list and detail |
| `GET /gallery` | Gallery items (visible only) |
| `GET /testimonials` | Approved testimonials only |
| `GET /settings` | Contact details, hours, social links |
| `GET /media/{name}` | Uploaded image files |
| `POST /enquiries/consultation`, `/order`, `/laundry`, `/contact` | The four forms. `/order` is multipart (reference pictures); the others are JSON. A hidden `website` field is the honeypot and must stay empty. |

**Admin** (everything under `/admin` needs `Authorization: Bearer <token>` except login and password reset)

| Route | What it does |
| --- | --- |
| `POST /admin/login`, `GET /admin/me` | Sign in; current admin |
| `POST /admin/password-reset/request`, `/confirm` | Password reset by email |
| `GET /admin/enquiries`, `GET/PATCH /admin/enquiries/{id}` | List, view, change status and notes |
| `GET /admin/enquiries/export.csv` | CSV export (Owner only) |
| `POST/PATCH/DELETE /admin/gallery` | Manage gallery items |
| `GET/PATCH /admin/services` | Edit services |
| `GET/POST/PATCH/DELETE /admin/testimonials` | Manage testimonials |
| `PATCH /admin/settings` | Edit contact details, hours, social links |
| `POST /admin/uploads/images` | Upload an image (re-encoded, metadata stripped) |

## Project layout

```
app/
  main.py        app factory, middleware, router wiring
  core/          config, security, rate limits, email, image storage
  db/            engine/session, Base, seed
  models/        SQLAlchemy tables
  schemas/       request and response models
  routers/       one file per area (public and admin)
alembic/         database migrations
tests/           pytest suite
```

## Development

| Task | Command |
| --- | --- |
| Run the API | `uv run fastapi dev` |
| Run the tests | `uv run pytest -q` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Apply migrations | `uv run alembic upgrade head` |
| New migration | `uv run alembic revision --autogenerate -m "message"` |
| Check models match the database | `uv run alembic check` |

The tests use an in-memory SQLite database, so they need no PostgreSQL. Line length is 120.

## Deployment checklist

The full reasoning is in `../DOCS/SECURITY-REVIEW.md`. Before launch:

1. `ENVIRONMENT=production`.
2. `JWT_SECRET` of 32+ random characters.
3. A strong, unique database password (not `goody`), a database reachable only from the API, and automated backups.
4. Serve over HTTPS only, behind a reverse proxy that sets a request-size limit (for example
   `client_max_body_size 30m`). Start the API with
   `--proxy-headers --forwarded-allow-ips=<proxy address> --no-server-header`. Without this, every visitor shares
   the proxy's address for rate limiting.
5. `CORS_ORIGINS`, `FRONTEND_URL` and `API_PUBLIC_URL` set to the real addresses.
6. `UPLOAD_DIR` on persistent, backed-up storage.
7. Run the seed once to create the Owner, then remove `OWNER_PASSWORD`.
8. Configure real email (`SMTP_*`, `MAIL_FROM`, `ENQUIRY_NOTIFY_TO`) and send a test enquiry and a test password reset.
9. Protect the admins' mailboxes: anyone who controls one can reset that account's password.

Rate limits are held in server memory, so run a single process, or move them to a shared store before scaling out.

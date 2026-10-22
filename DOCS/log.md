# Build Log: GOODYEXCELLENT COUTURE

A running record of what has been built, why, and how it was checked. The SRS (`SRS — GOODYEXCELLENT COUTURE Website.md`) stays the source of truth. Progress against it is tracked in `BACKEND-CHECKLIST.md`.

**Working agreement**
- Backend first (`uv`); the frontend (`bun`) starts only when every Must item in the checklist is ticked.
- One small feature per step, explained before moving on.
- A conventional commit message after every step.
- No endpoints in `app/main.py`; all routes live in `app/routers/`.
- PostgreSQL runs locally in Docker.

---

## Phase 0: First attempt (superseded)

**Date:** 2026-10-22 · **Commits:** `0512308`, `a0d11d7`

The backend was first scaffolded in large batches: all six models, every router stub, a seed script, public read endpoints and the full enquiry endpoints with email, rate limiting and tests. It worked (28 tests passing on SQLite) but was too much to follow.

**Outcome:** rejected as the wrong way to build. The `backend/` folder was reset and rebuilt one feature at a time. The old version stays in git history (`a0d11d7`) for reference.

**Lesson:** build one feature per step and explain each. Saved to memory.

---

## Phase 1: Rebuild, feature by feature

### Feature 1: App and `/health`
**Commit:** `123c760` (combined with the reset)
- Reset `backend/` to a bare `uv` project. Dependencies are added only when a feature needs them.
- `app/main.py` creates the FastAPI app; `GET /health` returns `{"status": "ok"}`.
- `pyproject.toml` sets `pythonpath = ["."]` so tests can import `app`.
- **Test:** `tests/test_health.py`.

### Feature 2: Configuration
**Commit:** `13886ee`
- `app/core/config.py`: a `Settings` class (pydantic-settings). Values come from environment variables, then a git-ignored `.env`, then defaults (SRS NFR-12).
- `.env.example` documents the variables.
- **Rule adopted:** a setting is added only when the feature using it arrives.
- **Tests:** default, environment override, unknown variables ignored.

### Feature 3: Database connection
**Commit:** `f1e7965`
- Added SQLAlchemy (async) and asyncpg; `database_url` setting.
- `app/db/session.py`: `engine`, `SessionLocal`, and the `get_session()` dependency (one session per request).
- `GET /health/db` runs `SELECT 1`; returns 503 if the database is down. Kept separate from `/health` so liveness never depends on the database.
- **Tests:** use in-memory SQLite via a `dependency_overrides` fixture in `tests/conftest.py`.

### Feature 4: Migrations and `site_settings`
**Commit:** `49087fd`
- Alembic (async template) wired to the app settings and `Base.metadata`.
- `app/db/base.py` (`Base`) and `app/models/site_settings.py`: a single-row table whose defaults carry the exact contact details from SRS 2.5.
- First migration `0e408dd5b05c`.

### Feature 5: Seed command
**Commit:** `3215a9e`
- `app/db/seed.py`: idempotent; inserts the `site_settings` row only if missing and never overwrites edits. Run with `uv run python -m app.db.seed`.
- **Tests:** creates the row with the right contacts; running twice keeps one row and preserves an edit.

### Infrastructure: Router folder and Docker
**Commit:** `f754da8` (two changes in one commit)
- **Refactor:** health endpoints moved to `app/routers/health.py`; `main.py` now only creates the app and includes routers.
- **Docker:** `backend/docker-compose.yml` runs PostgreSQL 17 (user, password and database all `goody`) with a named volume and a healthcheck.
- **Verified on real PostgreSQL:** migration applied, seed run twice (one row), `/health` and `/health/db` both ok.

### Feature 6: `GET /settings`
**Commit:** `73b4809`
- First real router and schema (`app/schemas/site_settings.py`, `app/routers/settings.py`). Models describe database rows; schemas describe API JSON.
- Returns 404 if settings have not been seeded. `id` is not exposed.
- Live check returned the seeded phone numbers, WhatsApp link and email.

### Feature 7: CORS
**Commit:** `a781593`
- `cors_origins` setting (default `http://localhost:3000`); `CORSMiddleware` in `main.py`. Only listed origins may call the API from a browser (SRS TS-01).
- **Tests:** an allowed origin gets the allow header; another origin gets 400; origins can be set from the environment.

### Feature 8: `services` table and seed
**Commit:** `173dd61`
- `app/models/service.py` (title, unique indexed `slug`, description, `image_url`, `display_order`, `visible`). Migration `cfbe0bbd0a63`, generated against real PostgreSQL.
- Seed adds the eight services from FR-19 by slug, so re-runs never duplicate or overwrite.
- Descriptions are placeholders ("Description to be supplied."). The approved brand copy is still needed (FR-21, CR-02).

### Feature 9: `GET /services` and `GET /services/{slug}`
**Commit:** `f51368f`
- Lists visible services in display order; detail by slug; 404 for unknown or hidden slugs.
- Introduced path parameters.
- Live-checked on PostgreSQL.

### Feature 10: `gallery_items` table
**Commit:** `63fbf25`
- `app/models/enums.py` (`GalleryCategory`: the seven FR-25 categories) and `app/models/gallery_item.py`. `created_at` is filled by the database.
- Migration `62deb755d6ec`. **Fixed by hand:** Alembic's `downgrade()` does not drop the PostgreSQL enum type, so `DROP TYPE gallerycategory` was added. An upgrade, downgrade and upgrade cycle was confirmed.
- `validate_strings=True` on the enum so the app rejects bad categories even on SQLite. PostgreSQL rejects them natively (checked in psql).
- No seed: the gallery needs the owner's real photos.

### Feature 11: `GET /gallery`
**Commit:** `49a2fcb` (committed together with Feature 12; the gallery endpoint has no commit of its own)
- Query parameters: `category` (enum), `featured` (three states), `limit` (1 to 100, default 50) and `offset`. Invalid values return 422.
- Ordered by `display_order`, then `id`.
- **Tests:** filters, combined filters, pagination, bad parameters, empty list. Live-checked with temporary rows, which were deleted afterwards.

### Feature 12: Testimonials
**Commit:** `49a2fcb`
- `app/models/testimonial.py`; `visible` defaults to hidden so nothing is published without owner approval (FR-49, CR-03).
- **Refinement:** `server_default=false()` so the safeguard also holds for raw SQL inserts. The migration was rolled back, regenerated and reapplied before committing (final revision `ecf95f018c21`).
- `GET /testimonials` returns approved ones only, newest first.
- Fixed a pytest warning (it tries to collect imported classes named `Test…`) by referencing `models.Testimonial`.

### Fix: `fastapi dev`
**Commit:** `a8bfb96`
- `uv run fastapi dev` failed because plain `fastapi` lacks the CLI. Switched to `fastapi[standard]` and removed the now-redundant `uvicorn` dependency.
- Added `[tool.fastapi] entrypoint = "app.main:app"`.
- `--bare` is not a uv flag; the bracketed extra needs quotes in bash.

---

## Current state

**Endpoints**

| Method and path | Purpose |
| --- | --- |
| `GET /health` | Process is alive |
| `GET /health/db` | Database reachable |
| `GET /settings` | Contact details, hours, socials |
| `GET /services`, `GET /services/{slug}` | Service lines |
| `GET /gallery` | Portfolio, filterable and paginated |
| `GET /testimonials` | Approved testimonials |

**Tables (migration chain):** `site_settings` (`0e408dd5b05c`) → `services` (`cfbe0bbd0a63`) → `gallery_items` (`62deb755d6ec`) → `testimonials` (`ecf95f018c21`).

**Tests:** 37 passing. They use in-memory SQLite. Real PostgreSQL has been checked by hand for migrations, the seed and each endpoint.

**Checklist:** 9 items ticked, 25 open (see `BACKEND-CHECKLIST.md`). Models: 4 of 6 done.

**Commands**

| Task | Command |
| --- | --- |
| Start PostgreSQL | `docker compose up -d db` |
| Apply migrations | `uv run alembic upgrade head` |
| Seed data | `uv run python -m app.db.seed` |
| Run the API | `uv run fastapi dev` |
| Run tests | `uv run pytest` |
| New migration | `uv run alembic revision --autogenerate -m "message"` |
| Check models match the database | `uv run alembic check` |

---

## Open items

**Waiting on the owner (SRS 6.2)**
- Approved service descriptions (replace the placeholders)
- Logo, photos, full address, map link, opening hours, social links, testimonials with consent

**Remaining backend**
- `enquiries` table, then one submission endpoint per form: consultation, order, laundry, contact
- Validation for Nigerian and international phone numbers; honeypot and rate limiting; email as a background task (saved first, so a mail failure never loses an enquiry)
- Reference image uploads and the image pipeline (WebP re-encoding)
- `admin_users` table; sign-in, Argon2 hashing and lockout; password reset by email
- Admin endpoints: gallery, services, testimonials, enquiries with status workflow and notes, settings
- Seed for the first Owner account
- Quality gates: security review, performance targets, README with setup and deployment

**Not started:** frontend (`frontend/` is the untouched `create-next-app` output; to be moved to `bun` when we reach it).

**Next feature:** the `enquiries` table.

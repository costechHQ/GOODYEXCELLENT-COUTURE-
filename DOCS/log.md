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

### Feature 13: `enquiries` table
**Commit:** see git log
- One table for all four forms (consultation, order, laundry, general), with a `type` column. Shared columns are required; type-specific ones are nullable and the API will decide what each form must supply. This keeps the admin list, search and status workflow (FR-53) simple.
- `app/models/enquiry.py` plus three enums in `enums.py`: `EnquiryType`, `ContactMethod`, `EnquiryStatus` (new, contacted, in_progress, completed, closed). `status` defaults to `new` in both Python and the database.
- `phone` is nullable because the contact form takes phone or email (FR-47); the endpoint will require at least one.
- `internal_notes` and `status` are staff-only and must never appear in public responses.
- Reference images are deliberately not here; they arrive with the upload feature.
- Migration `a3f1c9d27b45`, **written by hand** (Docker was not installed on this machine, so no autogenerate), with `DROP TYPE` for all three enums on downgrade. Checked by rendering the PostgreSQL SQL offline in both directions (`alembic upgrade/downgrade --sql`). **Still to do:** apply it to a real PostgreSQL and run `alembic check`.
- **Tests:** enum values match the SRS, defaults, a full order enquiry, unknown type rejected (41 passing).

### Feature 14: `POST /enquiries/consultation`
**Branch:** `feat/consultation-endpoint` (branched from `feat/enquiries-table`)
- **Branching rule adopted:** every feature gets its own branch. The enquiries table was moved from `main` to `feat/enquiries-table` and local `main` reset to `b4df15b`. Nothing had been pushed.
- `app/core/phone.py`: `normalise_phone` accepts Nigerian local (080...), `+234...`, `234...` and any other `+` international number (E.164), ignoring spaces, dashes, dots and brackets (FR-33). Numbers are stored in one canonical form, `+234...`.
- `app/schemas/enquiry.py`: `ConsultationIn` (FR-30) with trimmed, length-limited text, optional validated email, and `extra="forbid"` so clients can never set `status`, `internal_notes` or `type`. Email is required when it is the preferred contact method. No body measurements (FR-38).
- Phone is checked in a field validator so all field errors come back together, each against its own field (FR-32). The cross-field email rule only appears once the fields are valid.
- `app/routers/enquiries.py`: returns 201 with `{id, message}`; the message promises no response time (FR-34).
- Not yet in this endpoint: email notification, honeypot, rate limiting. Each gets its own feature.
- **Tests:** 72 passing (31 new): phone formats, required and invalid fields, staff fields rejected, nothing saved when invalid.

### Feature 15: `POST /enquiries/contact`
**Branch:** `feat/contact-endpoint` (branched from `feat/consultation-endpoint`)
- `ContactIn` in `app/schemas/enquiry.py` (FR-47): name, subject and message required; phone and email each optional, but at least one is required so staff can reply. Stored with type `general`; `preferred_contact` stays empty because this form does not ask for it.
- A blank phone or email (`""` or spaces, which is what an empty web form sends) counts as not provided, so it does not fail validation by itself.
- Phone reuses `normalise_phone`; unknown fields are rejected as in the consultation form.
- Same 201 `{id, message}` response. Still no email, honeypot or rate limiting.
- **Tests:** 89 passing (16 new).

### Feature 16: `POST /enquiries/laundry`
**Branch:** `feat/laundry-endpoint` (branched from `feat/contact-endpoint`)
- `LaundryIn` (FR-42): name, phone and garment types required; message optional. The garment types are one free-text field stored in `garment_type`, since the form takes a list as text (for example "Senator, kaftan").
- Stored with type `laundry`. Same phone normalising, rejection of unknown fields and 201 `{id, message}` response as the other forms. Still no email, honeypot or rate limiting.
- **Open question for the owner (SRS question 9):** does laundry include pick-up and delivery, and is it open to the public? This affects the page copy and perhaps an address field later.
- **Tests:** 122 passing.

### Feature 17: `POST /enquiries/order` (text fields)
**Branch:** `feat/order-endpoint` (branched from `feat/laundry-endpoint`)
- `OrderIn` (FR-31): the consultation contact fields plus garment type (required), occasion, needed-by date, quantity (1 to 500), fabric or colour preference and message (all optional). Stored with type `order`.
- **Refactor:** the shared name, phone, email and preferred-contact fields and checks moved into a private base class `_ContactDetails`, used by both `ConsultationIn` and `OrderIn`. The existing consultation tests passed unchanged.
- The needed-by date may be today but not in the past. "Today" is taken in Nigeria time (UTC+1), so a visitor's own calendar day is never rejected.
- **Not done: reference images (up to 5, 5 MB each).** They arrive with the upload and image pipeline. FR-31 is therefore only partly complete, and the checklist item stays open.
- **Tests:** 122 passing (20 new).

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

**Tables (migration chain):** `site_settings` (`0e408dd5b05c`) → `services` (`cfbe0bbd0a63`) → `gallery_items` (`62deb755d6ec`) → `testimonials` (`ecf95f018c21`) → `enquiries` (`a3f1c9d27b45`).

**Tests:** 122 passing. They use in-memory SQLite. Real PostgreSQL has been checked by hand for migrations, the seed and each endpoint.

**Checklist:** 9 items ticked, 25 open (see `BACKEND-CHECKLIST.md`). Models: 5 of 6 done.

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
- Order reference images (all four enquiry endpoints exist; consultation, contact, laundry and the order text fields are done)
- Validation for Nigerian and international phone numbers; honeypot and rate limiting; email as a background task (saved first, so a mail failure never loses an enquiry)
- Reference image uploads and the image pipeline (WebP re-encoding)
- `admin_users` table; sign-in, Argon2 hashing and lockout; password reset by email
- Admin endpoints: gallery, services, testimonials, enquiries with status workflow and notes, settings
- Seed for the first Owner account
- Quality gates: security review, performance targets, README with setup and deployment

**Not started:** frontend (`frontend/` is the untouched `create-next-app` output; to be moved to `bun` when we reach it).

**Next feature:** the enquiry safeguards, starting with the honeypot field shared by all four forms (FR-37).

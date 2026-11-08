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
- **Tests:** 342 passing.

### Feature 17: `POST /enquiries/order` (text fields)
**Branch:** `feat/order-endpoint` (branched from `feat/laundry-endpoint`)
- `OrderIn` (FR-31): the consultation contact fields plus garment type (required), occasion, needed-by date, quantity (1 to 500), fabric or colour preference and message (all optional). Stored with type `order`.
- **Refactor:** the shared name, phone, email and preferred-contact fields and checks moved into a private base class `_ContactDetails`, used by both `ConsultationIn` and `OrderIn`. The existing consultation tests passed unchanged.
- The needed-by date may be today but not in the past. "Today" is taken in Nigeria time (UTC+1), so a visitor's own calendar day is never rejected.
- **Not done: reference images (up to 5, 5 MB each).** They arrive with the upload and image pipeline. FR-31 is therefore only partly complete, and the checklist item stays open.
- **Tests:** 122 passing (20 new).

### Feature 18: Honeypot on all four forms
**Branch:** `feat/honeypot` (branched from `feat/order-endpoint`)
- Every form schema now inherits `_FormBase`, which holds the shared `extra="forbid"` rule and a `website` field. The frontend must render `website` as a hidden input (off-screen, `tabindex="-1"`, `autocomplete="off"`) and leave it empty; people never fill it, bots usually do (FR-37).
- When `website` is set, the API answers with the normal 201 and the same response shape (`id` is `0`) but saves nothing, so a bot gets no signal to adapt to. The value is never stored.
- **Refactor:** the four copy-pasted save blocks in `app/routers/enquiries.py` became one `_save()` helper, which is where the honeypot check lives.
- A submission that is invalid *and* has the honeypot set still returns 422; this is a minor, accepted leak.
- A honeypot stops simple bots only. Rate limiting (next) handles the rest; CAPTCHA only if abuse appears (FR-37).
- **Tests:** 132 passing (10 new, run against all four forms).

### Feature 19: Rate limiting on the enquiry forms
**Branch:** `feat/rate-limiting` (branched from `feat/honeypot`)
- `app/core/rate_limit.py`: an in-memory sliding-window `RateLimiter` (injectable clock for tests) and a `limit_enquiries` dependency applied to the whole enquiries router. Over the limit returns **429** with a `Retry-After` header.
- **Chosen over a database-backed limiter** for Release 1 (one small server): no new dependency or migration. Trade-off: counts reset on restart and are not shared between server processes. Revisit if the API is ever scaled out.
- Settings `RATE_LIMIT_MAX_REQUESTS` (10) and `RATE_LIMIT_WINDOW_SECONDS` (600), documented in `.env.example`.
- Counted per client IP across all four forms together. Every attempt counts, including invalid ones and honeypot hits, so it cannot be probed with bad data. Blocked attempts are not counted, so waiting out the window always works. Ten attempts leaves room for a visitor to fix typos.
- The IP comes from the connection (`request.client.host`). A client-sent `X-Forwarded-For` is deliberately ignored because anyone can forge it (tested). **Deployment note for the README:** behind a reverse proxy, every visitor would share the proxy's IP, so start the server with uvicorn's proxy-header support and a trusted-proxy list (`--proxy-headers --forwarded-allow-ips`). Until then the limiter would count all visitors as one.
- Idle clients are swept once more than 10,000 are tracked, so memory stays bounded.
- `tests/conftest.py` has an autouse fixture that empties the limiter around every test.
- **Tests:** 143 passing (11 new).

### Feature 20: Email notification for new enquiries
**Branch:** `feat/email-notifications` (branched from `feat/rate-limiting`)
- `app/core/mail.py`: builds a plain-text alert and sends it over SMTP using only the standard library (`smtplib`). **Chosen over a transactional email API** (Resend, SendGrid) for Release 1: no account, key or dependency. All sending sits behind `notify_new_enquiry`, so switching later means changing one function.
- **Saved first, then emailed (FR-35, TS-04, NFR-15):** `_save()` commits the enquiry, then queues the email as a FastAPI background task. It is a plain function, so it runs in a worker thread and a slow mail server cannot block other requests.
- **A mail failure never loses an enquiry or errors the visitor.** The error is logged with the enquiry id and the exception type only, never the visitor's name, phone or email.
- **Off until configured:** nothing is sent unless both `SMTP_HOST` and `ENQUIRY_NOTIFY_TO` are set. Other settings: `SMTP_PORT` (587), `SMTP_SECURITY` (`starttls`, `ssl` or `none`), `SMTP_USERNAME`, `SMTP_PASSWORD` (a `SecretStr`, hidden in logs and reprs), `MAIL_FROM`. All are in `.env.example`. 10-second SMTP timeout.
- Subject is `[New <type> enquiry] <name>`. `Reply-To` is the client's email when given, so staff reply straight from the inbox. The body lists only the fields that were filled in.
- **Header injection:** built with `EmailMessage`, which refuses newlines in headers, and the name in the subject is flattened to one line (tested).
- No email for honeypot hits or invalid submissions.
- **Not yet tested against a real mail server**, only a fake SMTP class. Before launch, send a real test enquiry through the chosen provider. Many providers (Gmail, Zoho) need an app password and require `MAIL_FROM` to be an address they own.
- **Needed from the owner (SRS 6.2, IF-02):** the enquiry inbox address and the mail account or provider to send from.
- **Not done:** the 1-minute delivery target (FR-58) can only be checked with a real server. The client auto-reply is a later release (FR-60).
- **Tests:** 160 passing (17 new).

### Merge: enquiries chain into `main`
The eight stacked branches (`feat/enquiries-table` through `feat/email-notifications`) were merged into `main` in order with `--no-ff`, one merge commit per feature (`57695ef` to `8841e1c`). `main` was pushed to GitHub. The `main` tree matched the last branch exactly and all 160 tests passed on it. The feature branches were kept. Three of them (`consultation-endpoint`, `laundry-endpoint`, `order-endpoint`) had already appeared on GitHub without being pushed from this session; they are redundant now.

### Feature 21: `admin_users` table
**Branch:** `feat/admin-users` (branched from `main`)
- `app/models/admin_user.py`: `email` (unique, indexed), `password_hash`, `role`, `is_active`, `created_at`. Only a hash is ever stored.
- `AdminRole` enum: `owner` and `staff` (FR-57). **The default is `staff`** (least privilege), so nobody becomes an Owner by accident; the first Owner is created explicitly by the seed.
- The model trims and lowercases `email` on assignment, so `Ada@X.com` and `ada@x.com` cannot become two accounts. The unique index then enforces it in the database.
- `is_active` lets an account be deactivated instead of deleted, keeping history intact.
- **Deliberately not here:** lockout counters and last-login time (they arrive with the sign-in and lockout feature, NFR-06) and the Argon2 library (arrives with sign-in).
- Migration `b7e2d4a81c36`, **written by hand** (no Docker here), with `DROP TYPE adminrole` on downgrade. Checked by rendering the PostgreSQL SQL offline in both directions. **Still to do:** apply it to a real PostgreSQL and run `alembic check`. The earlier hand-written enquiries migration has the same pending check.
- **Tests:** 165 passing (5 new).

### Feature 22: First Owner seed and password hashing
**Branch:** `feat/owner-seed` (branched from `feat/admin-users`, which is not merged yet)
- Added `argon2-cffi`. `app/core/security.py` wraps it: `hash_password` (Argon2id, library defaults) and `verify_password` (returns `False` for a wrong password or a malformed hash). The sign-in feature will reuse both (NFR-06).
- **Chosen over a random printed password:** the Owner comes from `OWNER_EMAIL` and `OWNER_PASSWORD`, so no password lives in the repo and none is printed or logged. Both are in `.env.example`.
- `seed_owner()` in `app/db/seed.py`, called by the existing seed:
  - Does nothing if neither variable is set (a fresh clone and the tests need no setup).
  - Creates the Owner only if **no Owner exists yet**. A leftover `OWNER_EMAIL` on a server can never add a second Owner, and re-running never resets the password. A Staff account does not block it.
  - Stops with a clear message and creates nothing if only one variable is set, the email is invalid, or the password is under 12 characters. The password never appears in an error.
- **After the first run, remove `OWNER_PASSWORD` from the environment.**
- Note: the email validator rejects reserved test domains such as `.test`; real addresses are unaffected. Tests use `example.com`.
- **Not yet run against real PostgreSQL** (no Docker here); verified on SQLite only.
- **Tests:** 177 passing (12 new).

### Merge: admin branches into `main`
`feat/admin-users` and `feat/owner-seed` were merged into `main` with `--no-ff` (`87dc07d`, `51d50b0`). 177 tests passed on `main`. Not pushed: `main` is 4 commits ahead of GitHub at this point.

### Feature 23: Admin sign-in (`POST /admin/login`, `GET /admin/me`)
**Branch:** `feat/admin-login` (branched from `main`)
- **Token delivery chosen: a Bearer token in the JSON response**, not a cookie. The frontend sends `Authorization: Bearer ...`. No CSRF risk because browsers do not attach it automatically, and the CORS config already allows the header. Added `pyjwt`.
- `POST /admin/login` returns `{access_token, token_type: "bearer", expires_in}`. Lifetime is `ACCESS_TOKEN_MINUTES` (60).
- The token carries only `sub` (the account id), `iat` and `exp`. **Role and active status are read from the database on every request**, so deactivating an account cuts off an unexpired token at once.
- **One identical 401** for unknown email, wrong password and deactivated account. For an unknown email a dummy Argon2 check is still spent, so response time does not reveal which emails exist.
- **No default secret.** `JWT_SECRET` must be at least 32 random characters; without it login returns 503 and tokens are refused. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Token reading pins HS256 and requires `exp` and `sub`; expired, tampered, wrong-secret, `alg: none` and expiry-less tokens are all refused (tested).
- `app/core/auth.py`: `get_current_admin` (the FR-51 guard for every admin route; use the `CurrentAdmin` alias) and `require_owner` (403 for Staff, FR-57). `GET /admin/me` is the first protected route and returns id, email, role and created date, never the hash.
- **Not done: failed-login lockout (NFR-06). Until it lands, login has no brute-force protection, so do not deploy before the next feature.** Password reset (FR-56) also still to do.
- **Tests:** 206 passing (29 new).

### Feature 24: Failed-login lockout (NFR-06)
**Branch:** `feat/login-lockout` (branched from `feat/admin-login`, which is not merged yet)
- **Chosen over a per-IP login limit:** a temporary lock on the account. After `LOGIN_MAX_FAILURES` (5) wrong passwords in a row the account locks for `LOGIN_LOCK_MINUTES` (15). Both are settings in `.env.example`.
- New `admin_users` columns `failed_login_attempts` and `locked_until`. Migration `c4d8e1f95a27`, **hand-written** (no Docker); the PostgreSQL SQL was checked offline in both directions. Still to run on a real PostgreSQL, with the other two hand-written migrations.
- The counter is incremented inside the database, so two simultaneous guesses are both counted. It resets on a good sign-in and when a lock begins.
- **A lock is invisible from outside.** A locked account refuses even the correct password with the same generic 401 and no `Retry-After`, and still spends a password check, so neither the response nor its timing reveals the lock. Attempts during a lock are not counted and do not extend it, so an attacker cannot keep the real owner locked out indefinitely.
- A deactivated account with the right password is refused and not counted.
- **Known gap:** unknown emails have no account to count against, so guessing *which* emails exist is not slowed here (and the response gives nothing away anyway). A per-IP limit on `/admin/login` could be added later if needed.
- **Trade-off:** an attacker can still lock a known admin's account by guessing wrongly 5 times every 15 minutes. That is accepted for Release 1; the Owner can wait it out.
- Test note: SQLite returns naive datetimes, so the lock check treats a naive `locked_until` as UTC; PostgreSQL returns aware ones.
- Test warnings: the suite shows 3 to 5 intermittent `PytestUnhandledThreadExceptionWarning`s from `aiosqlite` threads closing after the event loop in tests that mix the synchronous `TestClient` with async fixtures. They were already present before this feature (confirmed by stashing). Harmless, but worth tidying later.
- **Tests:** 221 passing (15 new).

### Merge: login branches into `main`
`feat/admin-login` and `feat/login-lockout` were merged into `main` with `--no-ff` (`8f271b5`, `af7a713`). 221 tests passed on `main`. Not pushed: `main` was 8 commits ahead of GitHub.

### Feature 25: Gallery admin API (create, edit, delete)
**Branch:** `feat/gallery-admin` (branched from `main`)
- `app/routers/admin_gallery.py`: `POST /admin/gallery` (201), `PATCH /admin/gallery/{id}`, `DELETE /admin/gallery/{id}` (204). The whole router is behind `get_current_admin` (FR-51), so Owner and Staff can both use it (FR-52). Every route returns 401 without a valid token, and nothing changes when it is refused (tested).
- **Image URLs only for now:** `image_url` must be an absolute `http(s)` URL (max 500), so `javascript:`, `data:`, `ftp:` and relative paths can never be stored. File upload and the WebP pipeline come later (FR-29).
- `alt_text` is required and non-empty on create (CR-04). Text is trimmed. Unknown fields (for example `id`) are rejected.
- A new item goes to the end (`max(display_order) + 1`) unless `display_order` is given.
- `PATCH` changes only the fields sent. `caption` may be set to `null` to clear it; every other field rejects `null`. An empty body is a no-op. A missing item is 404.
- Admin responses add `display_order` and `created_at`; the public `GET /gallery` still shows neither.
- `DELETE` removes only the database row. There are no stored files yet; when uploads arrive, deleting must also remove the files.
- **Not done:** bulk reorder and feature toggles in one call (the single-item `PATCH` already sets `featured` and `display_order`), upload (FR-29), and a filter for the admin list (the public list covers it for now).
- **Tests:** 260 passing (39 new).

### Merge and push: gallery admin
`feat/gallery-admin` was merged into `main` (`--no-ff`), the 260 tests passed on `main`, and `main` was pushed to GitHub (`96a12a5`, 10 commits). A scan of the pushed diff found no secrets; only `.env.example` is tracked, with blank secret fields.

### Feature 26: Services admin (list and edit)
**Branch:** `feat/services-admin` (branched from `main`)
- `app/routers/admin_services.py`: `GET /admin/services` (every service, **hidden ones included**, so an admin can find and unhide them) and `PATCH /admin/services/{id}`. Behind `get_current_admin`; Owner and Staff may both edit (FR-52). Anonymous and bad-token requests get 401 and change nothing (tested).
- **Editable:** title, description, image URL, display order and visibility (FR-21). **The slug is read-only** (a `slug` field is rejected with 422) because it forms the public URL, so editing it would break links and search results.
- `PATCH` changes only the fields sent; only `image_url` may be set to `null` (to remove the picture); the other fields reject `null`. Text is trimmed; description up to 5,000 characters.
- **No create or delete:** the eight lines are fixed by FR-19 and FR-52 only asks for text editing. Hiding a service covers the rest (tested: POST and DELETE return 405).
- Edits show up on the public `GET /services/{slug}`, which still exposes neither `display_order` nor `visible`. A hidden service is 404 publicly.
- **Refactor:** the `http(s)`-only image URL rule moved into `app/schemas/common.py` (`ImageUrl`) and is shared by the gallery and services schemas. The gallery tests passed unchanged.
- The seeded descriptions are still the placeholder "Description to be supplied." The owner's approved copy can now be entered through this endpoint (FR-21, CR-02).
- **Tests:** 286 passing (26 new).

### Merge: services admin into `main`
`feat/services-admin` was merged into `main` with `--no-ff`; 286 tests passed on `main`. Not pushed.

### Feature 27: Enquiries admin, list and detail (read-only)
**Branch:** `feat/enquiries-admin-list` (branched from `main`)
- `app/routers/admin_enquiries.py`: `GET /admin/enquiries` and `GET /admin/enquiries/{id}`, both behind `get_current_admin` (FR-51, FR-53). Enquiries hold clients' personal details, so anonymous requests get 401 and no data appears in the response (tested). There is no public way to read them.
- The list is **newest first** (`created_at` descending, then `id` descending, so equal timestamps stay stable). Filters: `type` and `status`; they combine. Pagination: `limit` (1 to 100, default 50) and `offset`. Bad values return 422.
- The list returns an envelope `{items, total, limit, offset}`; `total` counts all matches ignoring paging so the admin screen can page. This differs from the public lists, which return plain arrays.
- List rows are **summaries** (id, type, status, name, phone, email, preferred contact, service, subject, created date): no message and no internal notes. The detail route returns the whole record including `internal_notes` (FR-54).
- **Not done yet (each its own step):** text search over name, phone, email, subject and message; changing `status` and writing internal notes (`PATCH`); CSV export (FR-53).
- **Tests:** 307 passing (21 new).

### Merge: enquiries list into `main`
`feat/enquiries-admin-list` was merged into `main` with `--no-ff`; 307 tests passed on `main`. Not pushed.

### Feature 28: Enquiries admin, status and internal notes
**Branch:** `feat/enquiries-admin-update` (branched from `main`)
- `PATCH /admin/enquiries/{id}` (FR-53, FR-54), behind `get_current_admin`. Anonymous and bad-token requests get 401 and change nothing (tested). Returns the full detail record.
- **Only `status` and `internal_notes` are editable.** Everything the client submitted (name, phone, email, message, type, garment details, dates) is read-only: any other field is rejected with 422 and the stored values are unchanged (tested field by field). Staff cannot alter what a client actually sent.
- **Any status may follow any other** (New, Contacted, In Progress, Completed, Closed), because FR-53 sets no order. A Closed enquiry can be reopened. `status` cannot be null or an unknown value.
- Notes are **replaced, not appended**; `null` clears them; blank or over 5,000 characters is rejected; text is trimmed. Sending only one of the two fields leaves the other untouched.
- Notes never appear in any public response (tested). Enquiries cannot be created or deleted through the admin routes (405).
- **Not recorded:** who changed a status or note, or when. If the owner wants an audit trail (for example for disputes between staff), it needs its own table; raise it before launch.
- **Tests:** 342 passing (35 new).

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
| `POST /enquiries/consultation`, `/order`, `/laundry`, `/contact` | Public forms (honeypot, rate limit, email alert) |
| `POST /admin/login`, `GET /admin/me` | Admin sign-in (Bearer JWT) and current admin |
| `POST /admin/gallery`, `PATCH`/`DELETE /admin/gallery/{id}` | Gallery management (admin only) |
| `GET /admin/services`, `PATCH /admin/services/{id}` | Services text editing (admin only) |
| `GET /admin/enquiries`, `GET`/`PATCH /admin/enquiries/{id}` | Enquiry list (filter, page), detail, and status/notes update (admin only) |

**Tables (migration chain):** `site_settings` (`0e408dd5b05c`) → `services` (`cfbe0bbd0a63`) → `gallery_items` (`62deb755d6ec`) → `testimonials` (`ecf95f018c21`) → `enquiries` (`a3f1c9d27b45`) → `admin_users` (`b7e2d4a81c36`) → admin lockout columns (`c4d8e1f95a27`).

**Tests:** 342 passing. They use in-memory SQLite. Real PostgreSQL has been checked by hand for migrations, the seed and each endpoint.

**Checklist:** 9 items ticked, 25 open (see `BACKEND-CHECKLIST.md`). Models: 6 of 6 done.

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
- Real-server check of enquiry email (code done, tested with a fake SMTP only)
- Reference image uploads and the image pipeline (WebP re-encoding)
- Password reset by email; password reset by email
- Admin endpoints: gallery, services, testimonials, enquiries with status workflow and notes, settings
- Seed for the first Owner account
- Quality gates: security review, performance targets, README with setup and deployment

**Not started:** frontend (`frontend/` is the untouched `create-next-app` output; to be moved to `bun` when we reach it).

**Next feature:** text search on the enquiries list (a `q` parameter), then CSV export (FR-53).

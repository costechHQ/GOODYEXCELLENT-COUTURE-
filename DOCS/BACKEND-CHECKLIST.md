# Backend Checklist

Derived from `SRS — GOODYEXCELLENT COUTURE Website.md`, which stays the source of truth. If this file and the SRS disagree, the SRS wins. Frontend work starts only when every **Must** item below is checked.

## Foundation
- [x] `uv` project, FastAPI app, async SQLAlchemy + asyncpg (TS-02), verified on SQLite only; real PostgreSQL check pending
- [x] Config from environment variables only (NFR-12)
- [ ] CORS restricted to the site's domain (TS-01)
- [ ] Models for the six entities in SRS 6.1 (1 of 6: site_settings)
- [x] Alembic wired to app settings and model metadata
- [ ] Initial Alembic migration generated and applied to PostgreSQL (needs a running DB: `docker compose up -d db`)
- [ ] Seed script: 8 services (FR-19), site settings with exact contact details (SRS 2.5), first Owner admin

## Public API
- [ ] Services list and detail by slug (FR-19, FR-21, FR-23) — Must
- [ ] Gallery list with category filter and featured flag (FR-24, FR-25, FR-09) — Must
- [ ] Testimonials: approved only (FR-12, FR-49) — Should
- [ ] Site settings read (FR-03, FR-44) — Must
- [ ] Consultation enquiry (FR-30) — Must
- [ ] Order enquiry: text fields done; reference image upload (up to 5, 5 MB each) pending (FR-31) — Must
- [ ] Laundry enquiry (FR-42) — Should
- [ ] General contact message (FR-47) — Must
- [ ] Server-side validation incl. Nigerian and international phone formats (FR-32, FR-33, NFR-07) — Must
- [ ] Honeypot and rate limiting (FR-37) — Must
- [ ] Enquiry saved before email; email sent as background task within 1 minute (FR-35, FR-58, TS-04, NFR-15) — Must

## Admin API
- [ ] Sign-in, JWT, protected routes (FR-51) — Must
- [ ] Argon2 hashing and failed-login lockout (NFR-06) — Must
- [ ] Password reset by email (FR-56) — Must
- [ ] Gallery: upload, caption, categorise, reorder, feature, delete (FR-28) — Must
- [ ] Upload: JPG/PNG/WebP only, size limit, re-encoded to WebP with resized variants (FR-29, NFR-04, NFR-08)
- [ ] Services text editing (FR-21, FR-52) — Must
- [ ] Testimonials add, edit, hide, delete (FR-50) — Should
- [ ] Enquiries: list, search, filter, export, status workflow (FR-53) — Must
- [ ] Enquiry internal notes (FR-54) — Should
- [ ] Site settings editing (FR-55) — Should

## Quality gates
- [ ] Tests cover every Must item above
- [ ] `uv run ruff check .` and `uv run pytest` pass
- [ ] Form responses in 2 s or less under normal load (NFR-05)
- [ ] Gallery endpoint stays fast with 500 items (NFR-29)
- [ ] Basic security review: no critical or high issues (SRS 8.3)
- [ ] README covers setup and deployment (NFR-27)

## Later releases (not part of this gate)
FR-39 booking, FR-43 care tips, FR-57 staff roles (column already exists), FR-60 auto-reply.

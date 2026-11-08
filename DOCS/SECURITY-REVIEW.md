# Security Review: GOODYEXCELLENT COUTURE API

**Date:** 2026-11-08 · **Scope:** the whole FastAPI backend at `main` plus the `chore/security-review` fixes · **Standard:** SRS 8.3 ("no critical or high issues") and NFR-06

**What this is, and is not.** A systematic review by the developer, backed by automated checks and permanent regression tests. It is **not** an independent penetration test. The frontend does not exist yet, so everything that depends on it (output escaping, token storage, the reset page) is listed as a requirement at the end.

**Result: no critical or high issues were found.** Five medium and low issues were found and fixed (F1 to F5). The residual risks (R1 to R13) are accepted or belong to deployment; the deployment list is mandatory before launch.

---

## How it was reviewed

| Check | Method | Outcome |
| --- | --- | --- |
| Authentication on every admin route | Regression test calls all 16 guarded admin operations, listed from the OpenAPI schema, with no token, a forged token and a wrong scheme | All answer 401 |
| Authorisation (Owner vs Staff) | The same routes called with a Staff token | Exactly one route is Owner-only (CSV export) |
| What the public can change | Test lists every non-admin route that writes | Exactly the four enquiry forms |
| Mass assignment | Test checks every request model rejects unknown fields | 14 of 14 do |
| Injection | Searched for raw SQL, `eval`, `exec`, `pickle`, `subprocess`, shell calls | None; the only raw SQL is a constant `SELECT 1` |
| Secrets | Scanned the **full git history** for private keys, cloud and GitHub tokens, credential-looking assignments and sensitive file names | Nothing; only `.env.example` (blank secrets) is tracked |
| Dependencies | `pip-audit` against the 72 pinned runtime packages | No known vulnerabilities |
| Logging | Read every log call | Only exception *type names* and ids; never addresses, tokens, names or paths |
| Error leakage | Forced an unexpected failure containing a fake password | Visitor sees a generic 500 |
| Real server | Ran uvicorn in production mode against PostgreSQL and inspected live responses | Headers, 404 docs, 401, CORS and 413 all correct |
| Every protection | **Mutation checks:** each fix was removed in turn to confirm a test fails | 10 of 11 caught; the 11th is an equivalent change (see F1) |

## Findings fixed in this review

| # | Severity | Issue | Fix | Test |
| --- | --- | --- | --- | --- |
| F1 | Medium | `/docs`, `/redoc` and `/openapi.json` were public in every environment, handing an attacker a complete map of every route | Switched off when `ENVIRONMENT=production` (app now built by `create_app()`) | `test_in_production_the_docs_and_schema_are_off` |
| F2 | Low | No browser safety headers | `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a strict `Content-Security-Policy` on every response (including errors and CORS preflights), and `Strict-Transport-Security` in production | `test_every_response_carries_the_safety_headers` and others |
| F3 | Low/Medium | Admin answers hold clients' personal details but could be cached | `Cache-Control: no-store` on everything under `/admin`, even refusals | `test_admin_answers_are_never_cached` |
| F4 | Medium | `/admin/login` had a per-account lockout but no per-address limit. Because every attempt (even for an unknown email) costs a deliberately slow Argon2 check, unauthenticated callers could burn CPU, and one machine could try one password against many accounts | 20 attempts per address per 10 minutes, counted across accounts, using the connection address (a forged `X-Forwarded-For` is ignored) | four tests in `test_security.py` |
| F5 | Medium | Only the two upload routes had a request-size cap, so a huge JSON body anywhere else would be read into memory before validation | 1 MB default cap on every POST, PUT and PATCH, applied before the body is read | `test_ordinary_requests_have_a_one_megabyte_limit` |

*Mutation 5 (leaving `docs_url` on in production) changes nothing, because FastAPI serves the docs page only when the schema URL also exists; the real switch, `openapi_url`, is guarded (mutation 6 fails a test).*

## Verified as sound

- **Passwords:** Argon2id; 12 to 128 characters; never logged or returned; an unknown email, a wrong password, a locked account and a deactivated account all give the identical 401 and spend the same hashing time.
- **Sign-in tokens:** HS256 pinned (the token's own algorithm header is never trusted); `exp`, `sub` and `iat` required; `alg: none`, expired, wrong-secret and tampered tokens refused; no default secret (sign-in is off until a 32+ character secret is set); role and active status read from the database on every request, so deactivating an account or changing a password ends sessions at once.
- **Lockout and limits:** 5 failures lock an account for 15 minutes invisibly (no `Retry-After`, no different message); per-address limits on sign-in, password reset and the enquiry forms.
- **Password reset:** answer identical for everyone; 256-bit single-use token stored only as a SHA-256 hash; 30-minute expiry; link built from `FRONTEND_URL`, never from the request's Host header; token in the URL fragment so it stays out of logs and Referer headers.
- **Uploads:** file type judged by decoding, never by name or declared type; metadata and GPS stripped; size, pixel and animation limits; random server-chosen names; only exactly-shaped names are ever read, written or deleted; deletion is reference-counted and ignores anything not under our own `/media/` address.
- **Output safety:** CSV export neutralises spreadsheet formulas; email headers cannot be injected; image and social links must be `https`.
- **Data exposure:** public reads return only approved or visible records and never staff-only fields; `reference_images` load only where asked for.
- **CORS:** only the configured origins, no credentials, an explicit method and header list.

## Residual risks (accepted, or handled at deployment)

| # | Risk | Rating | Note |
| --- | --- | --- | --- |
| R1 | The lockout lets an attacker who knows an admin's email lock that account for 15 minutes, repeatedly | Low | The owner can wait it out or reset the password. Accepted for Release 1. |
| R2 | No logout or token revocation; tokens last 60 minutes | Low | Mitigated: deactivation and password change end sessions immediately. |
| R3 | The password-reset request does one extra database write for a real admin, so timing differs very slightly | Low | Not practically exploitable over a network; accepted. |
| R4 | Rate limits live in server memory: reset on restart, not shared between processes, and behind a reverse proxy every visitor shares the proxy's address unless the server is told to trust it | Medium | **Deployment:** run with `--proxy-headers --forwarded-allow-ips=<proxy address>`; use a shared store if ever scaled to several processes. |
| R5 | Uploaded pictures (including clients' reference photos) are served from public but unguessable addresses (128-bit random names) | Low | Not suitable for confidential images. |
| R6 | No CAPTCHA; honeypot and rate limits only | Low | The SRS allows this until abuse appears (FR-37). |
| R7 | No total disk quota and no malware scan on uploads | Low/Medium | Each visitor is limited by the rate limit and 25 MB per order; monitor disk use. |
| R8 | The `server: uvicorn` response header reveals the software | Info | **Deployment:** run with `--no-server-header`. |
| R9 | The request-size cap judges only the *declared* length; a client streaming without one is stopped only by per-file read limits | Medium | **Deployment:** the reverse proxy must set its own request-size limit (for example `client_max_body_size 30m`). |
| R10 | The default database credentials (`goody` / `goody`) are for local development only | **High if left unchanged** | **Deployment:** use a strong, unique database password, a private network and backups. |
| R11 | There is no record of which admin changed a status, note or setting | Low | Raise with the owner if staff disputes are a concern. |
| R12 | Rotating `JWT_SECRET` signs every admin out | Info | Expected behaviour. |
| R13 | There is no API to create or manage admin accounts beyond the Owner seed (FR-57 "Could") | Info | A functional gap, not a vulnerability: extra Staff accounts currently need a database insert. |

## Mandatory before launch (deployment checklist)

1. `ENVIRONMENT=production` (turns off the docs and schema, turns on HSTS).
2. `JWT_SECRET`: 32 or more random characters (`python -c "import secrets; print(secrets.token_urlsafe(48))"`).
3. A strong, unique database password; the database reachable only from the API; automated backups (R10).
4. Serve over HTTPS only, behind a reverse proxy that sets a request-size limit (R9). Start the API with `--proxy-headers --forwarded-allow-ips=<proxy> --no-server-header` (R4, R8).
5. `CORS_ORIGINS` set to the website's real address only; `FRONTEND_URL` and `API_PUBLIC_URL` set to the real addresses.
6. `UPLOAD_DIR` on persistent, backed-up storage.
7. Create the Owner with `OWNER_EMAIL` / `OWNER_PASSWORD` for one run of the seed, then **remove `OWNER_PASSWORD`**.
8. Configure real email (`SMTP_*`, `MAIL_FROM`, `ENQUIRY_NOTIFY_TO`) and send a test enquiry and a test password reset.
9. Protect the admins' mailboxes (anyone who controls one can reset that account's password).

## Requirements for the frontend

- **Escape all text** returned by the API (names, messages, notes, captions, testimonials). The API stores text as typed; output escaping is the defence against stored cross-site scripting.
- Keep the admin token in memory (or another storage the owner is comfortable with) and send it as `Authorization: Bearer`; never put it in a URL.
- The reset page must read the token from `location.hash`, POST it to `/admin/password-reset/confirm`, then clear the address bar.
- Render the honeypot field `website` hidden (off-screen, `tabindex="-1"`, `autocomplete="off"`) and leave it empty. Send the order form as `FormData`.
- Set a Content-Security-Policy on the website itself; this API's policy does not cover the pages it serves data to.

## Keeping it this way

`backend/tests/test_security.py` fails if a future change adds an admin route without the guard, adds a public route that changes data, adds a request model that accepts unknown fields, exposes the docs in production, drops a safety header or the `no-store` rule, or removes the sign-in limit or the request-size cap. Re-run `pip-audit` and this review before each major release.

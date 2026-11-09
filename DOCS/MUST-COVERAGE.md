# Must requirements: backend test coverage

Maps each backend-relevant **Must** requirement in the SRS to the tests that protect it. Requirements that are purely
about pages and layout (FR-01 to FR-05, FR-07, FR-08, FR-10, FR-13 to FR-16, FR-26, FR-40, FR-41, FR-24's lazy
loading, FR-32's client-side half, FR-34's on-screen message, FR-20's button) belong to the frontend and are
tested there. The API-side value they depend on is listed below.

Last run: 744 tests passing (`uv run pytest -q`).

| Requirement | What the backend must do | Tests |
| --- | --- | --- |
| FR-09 | Featured items can be requested | `test_gallery_router` (`filter_featured`, `filters_combine`) |
| FR-19 | Eight services with exact titles and descriptions | `test_must_requirements` (`fr19`), `test_seed`, `test_services_router` |
| FR-20 | Service names are accepted by the enquiry forms | `test_consultation`, `test_order` |
| FR-21, FR-52 | Admin edits service text | `test_admin_services` |
| FR-25 | Exactly seven categories, filterable | `test_must_requirements` (`fr25`), `test_gallery_router`, `test_gallery_item_model` |
| FR-28, FR-52 | Admin uploads, captions, categorises, reorders, features, deletes gallery items | `test_admin_gallery`, `test_image_upload`, `test_image_cleanup` |
| FR-30 | Consultation form fields; contact methods are whatsapp, call, email | `test_consultation`, `test_must_requirements` (`fr30`) |
| FR-31 | Order form fields; up to 5 pictures of 5 MB each | `test_order`, `test_order_images`, `test_must_requirements` (`fr31`) |
| FR-32 | Server-side validation with errors reported per field | `test_consultation` (`field_errors_are_reported_together...`), every form's `invalid_values` and `required_fields` tests |
| FR-33 | Nigerian and international phone numbers | `test_phone` |
| FR-34 | Confirmation, with no promised response time | `test_must_requirements` (`fr34`) |
| FR-35, FR-58, IF-02 | Saved, then emailed in the background; a mail failure never loses the enquiry | `test_mail` |
| FR-37 | Honeypot and rate limiting | `test_honeypot`, `test_rate_limit` |
| FR-44, FR-04, FR-05 | Both phone numbers, WhatsApp link, email and location are served | `test_seed`, `test_settings_router`, `test_admin_settings` |
| FR-47 | General contact form | `test_contact` |
| FR-49, FR-52 | Only approved testimonials are public; admin manages them | `test_testimonials`, `test_admin_testimonials` |
| FR-51 | Sign-in required for the whole admin area | `test_admin_login`, `test_login_lockout`, `test_security` (every admin route refuses no, forged and wrong-scheme tokens) |
| FR-53 | View, search, filter, export, five statuses | `test_admin_enquiries`, `test_admin_enquiries_search`, `test_admin_enquiries_export`, `test_admin_enquiry_update`, `test_must_requirements` (`fr53`) |
| FR-56 | Password reset by email | `test_password_reset` |
| IF-05 | Image storage and delivery | `test_image_upload`, `test_order_images`, `test_image_cleanup` |

## Not provable by automated tests

- **FR-58, "within 1 minute":** tests prove the email is sent right after the response; actual delivery time depends on the
  mail provider. Check with a real mailbox once `SMTP_*` is configured.
- **IF-02, IF-05 against real services:** tests use a fake SMTP server and local disk storage.
- **FR-21 approved copy:** service descriptions are still placeholders until the owner supplies them.

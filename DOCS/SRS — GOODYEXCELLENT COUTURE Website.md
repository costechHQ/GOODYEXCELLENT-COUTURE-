# SRS — GOODYEXCELLENT COUTURE Website

Oct 16, 2026 · @Onyedika Christopher

## 1. Introduction

This document specifies the requirements for the official website of GOODYEXCELLENT COUTURE, a bespoke fashion and tailoring brand in Enugu, Nigeria. It is the agreed reference for designers, developers, and the brand owner while the site is designed, built, tested, and launched.

### 1.1 Purpose

The website must present the brand as a premium, reliable bespoke fashion house and turn visitors into consultations, orders, and WhatsApp conversations. This SRS defines what the site must do and the quality it must meet. It does not fix the visual design, which is settled in the design phase. The technology stack is fixed in Section 2.7.

### 1.2 Scope

**In scope (Release 1):**

- A responsive marketing website with Home, About, Services, Gallery, Consultation, Garment Care & Laundry, and Contact pages.
- Lead capture through consultation and order-enquiry forms, plus direct WhatsApp, phone, and email contact.
- A portfolio gallery of the brand's work.
- An admin area where the brand owner can update gallery items, service details, and testimonials, and view enquiries.
- Search engine optimisation, analytics, and basic security and backup measures.

**Out of scope (Release 1):**

- Online payment and a full shopping cart. Bespoke garments depend on measurements and consultation, so orders are agreed through enquiry first. This is an assumption to confirm (see Section 9.3).
- Native mobile applications.
- Automated measurement capture by camera or AI.

### 1.3 Definitions and Abbreviations

| Term | Meaning |
| --- | --- |
| SRS | Software Requirements Specification |
| Bespoke | Garments made to an individual customer's measurements and style choices |
| Visitor | Any person browsing the public website |
| Client | A visitor who has made an enquiry or booked a consultation |
| Admin | A brand staff member who manages the website through the admin area |
| CMS | Content Management System, the admin tools for editing site content |
| CTA | Call to action, such as a WhatsApp or consultation button |
| SEO | Search Engine Optimisation |
| MVP | Minimum viable product, the first release |

### 1.4 References

- GOODYEXCELLENT COUTURE brand information document (brand details, services, vision, mission, and values), supplied by the brand owner.
- Requirement priorities use MoSCoW: **Must**, **Should**, **Could**, **Won't (this release)**.

### 1.5 Document Overview

Section 2 describes the product and its users. Sections 3 to 6 hold the functional, interface, non-functional, and content requirements. Section 7 covers design and branding guidance, Section 8 covers risks, phasing, and acceptance, and Section 9 holds the sitemap, a traceability table from the brand information to requirements, and the open questions.

## 2. Overall Description

The website is a standalone, mobile-first brand and lead-generation site that lets customers discover GOODYEXCELLENT COUTURE, view its work, and start a bespoke order through consultation, WhatsApp, phone, or email.

### 2.1 Product Perspective

The site is the brand's primary online presence and complements its existing channels (phone and WhatsApp). It has no dependency on an internal ERP or inventory system. It integrates with WhatsApp click-to-chat, email delivery, an embedded map, and web analytics.

**Brand context**

| Item | Detail |
| --- | --- |
| Brand | GOODYEXCELLENT COUTURE |
| Motto | Dress Excellently and Be Different. |
| Location | Enugu, Nigeria |
| Category | Bespoke fashion and tailoring |
| Primary market | Men's fashion, with selected women's traditional outfits |
| Positioning | Premium bespoke brand built on excellence, craftsmanship, quality, reliability, and customer satisfaction |
| Values | Excellence, Reliability, Professionalism, Attention to Detail, Customer Satisfaction, Integrity |

### 2.2 Product Functions (Summary)

- Present the brand story, vision, mission, and values.
- Showcase the eight service lines and the garment care and laundry service.
- Display a filterable portfolio of past work.
- Capture consultation requests and order enquiries.
- Offer one-tap WhatsApp, call, and email contact on every page.
- Give the brand owner a simple admin area to keep content current.

### 2.3 User Classes

| User class | Description | Main goals |
| --- | --- | --- |
| Prospective customer | Man, or woman seeking senator wear, who finds the brand through search, social media, or referral | See quality of work, understand services, make contact |
| Returning customer | Existing client | Reorder, ask about laundry, contact the brand quickly |
| Event and corporate buyer | Groups ordering for weddings, ceremonies, or office wear | Enquire about multiple garments and timelines |
| Admin / brand owner | Staff who run the brand | Update gallery and content, read and follow up enquiries |
| Developer / maintainer | Technical support | Deploy, monitor, and maintain the site |

### 2.4 Operating Environment

- Public site works on current versions of Chrome, Safari, Firefox, Edge, and Samsung Internet, on Android, iOS, and desktop.
- Mobile phones are the expected main device, often on slower mobile data connections.
- Hosted on a reliable cloud or managed host with HTTPS and a custom domain.

### 2.5 Design and Implementation Constraints

- Contact details must match the brand record exactly: phone +2348060036531 and +2349024662143, WhatsApp link https://wa.me/2348060036531, email goodnessngwuta@gmail.com.
- Pages must stay usable on low bandwidth, so images need optimisation.
- Content is English. Nigerian English spelling and tone are acceptable.
- Prices are not published unless the owner provides them. The brand information already directs customers to enquire for laundry pricing, and the same approach is assumed for other services.
- The brand information contains no logo files, photography, or colour palette. The owner must supply these as inputs.

### 2.6 Assumptions and Dependencies

- The owner supplies logo, photos of finished work, and testimonials with the clients' permission.
- Enquiries are followed up manually by staff through WhatsApp, phone, or email.
- A domain name and hosting account will be registered in the brand's name.
- A business email address on the new domain is preferred over the current Gmail address but is optional.

### 2.7 Technology Stack

The site is built on the owner's chosen stack: a Next.js frontend and a FastAPI backend over PostgreSQL.

| Layer | Technology | Role on this site |
| --- | --- | --- |
| Frontend framework | Next.js (App Router) | Server-rendered or pre-rendered public pages for fast loads and SEO (NFR-01 to NFR-05, NFR-19 to NFR-22), plus the admin area |
| UI components | shadcn/ui (built on Tailwind CSS) | Accessible base for forms, dialogs, tables, and navigation (NFR-17) |
| Backend API | FastAPI, Python, asynchronous | REST endpoints for enquiries, gallery, services, testimonials, settings, and admin authentication |
| Database | PostgreSQL | Stores the entities in Section 6.1 |
| Migrations | Alembic | Every schema change ships as a versioned migration |

**Stack requirements**

- **TS-01:** The frontend and the API are separate services. The frontend calls the API over HTTPS, and the API allows cross-origin requests only from the site's own domain.
- **TS-02:** The API uses an asynchronous database engine and async endpoints. Alembic is normally paired with SQLAlchemy, so the ORM and driver choice (for example asyncpg) is confirmed in the design phase.
- **TS-03:** FastAPI's Pydantic models perform the server-side validation required by FR-32 and NFR-07.
- **TS-04:** Enquiry emails are sent as background tasks so form responses stay fast (NFR-05), and the enquiry is saved before the email is attempted (NFR-15).
- **TS-05:** Gallery and reference images are stored in object storage or a CDN, and PostgreSQL holds only their URLs (IF-05).
- **TS-06:** Hosting for the two services and a managed PostgreSQL instance is chosen in the design phase and must meet NFR-13 and NFR-14.

## 3. Functional Requirements

The site must deliver the 11 feature groups below. Each requirement has a unique ID (FR-xx) and a MoSCoW priority.

### 3.1 Global Navigation and Layout

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-01 | Every page shows a header with the brand logo, main navigation, and a visible "Book a Consultation" button. | Must |
| FR-02 | Navigation collapses into a mobile menu on screens narrower than 768 px. | Must |
| FR-03 | Every page shows a footer with the brand name, motto, phone numbers, email, WhatsApp link, location, and links to all main pages. | Must |
| FR-04 | A floating WhatsApp button opens a chat with +2348060036531 on every page. | Must |
| FR-05 | Phone numbers are tap-to-call links on mobile; the email is a mailto link. | Must |
| FR-06 | The site shows a branded 404 page with links back to Home and Contact. | Should |

### 3.2 Home Page

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-07 | A hero section displays the brand name, the motto "Dress Excellently and Be Different.", a hero image, and two buttons: "Book a Consultation" and "Chat on WhatsApp". | Must |
| FR-08 | A services overview shows cards for the main service lines, each linking to the Services page. | Must |
| FR-09 | A featured work section shows 6 to 8 selected gallery items. | Must |
| FR-10 | A "Why Choose Us" section presents the brand values: Excellence, Reliability, Professionalism, Attention to Detail, Customer Satisfaction, Integrity. | Must |
| FR-11 | A short "How It Works" section explains the bespoke process in steps (consult, measure, design and cut, fitting, delivery). The process steps are subject to owner confirmation. | Should |
| FR-12 | A testimonials strip displays approved client testimonials. | Should |
| FR-13 | A closing call-to-action block repeats the consultation and WhatsApp buttons. | Must |

### 3.3 About Page

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-14 | The page presents the brand story using the approved "About the Brand" text. | Must |
| FR-15 | The page presents the Vision and Mission statements in distinct sections. | Must |
| FR-16 | The page lists the six brand values with their descriptions. | Must |
| FR-17 | The page includes a closing statement with the motto and a contact CTA. | Should |
| FR-18 | The page can show a photo of the founder or workshop when the owner supplies one. | Could |

### 3.4 Services Page

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-19 | The page lists these services with a title, description, and representative image: Senator Wear, Kaftans, Suits and Formal Wear, Shirts, Trousers, Agbada and Chieftaincy Wears, Women's Senator Wear, Fashion Consultations. | Must |
| FR-20 | Each service has a "Request this" button that opens the order-enquiry form with that service preselected. | Must |
| FR-21 | Service descriptions use the approved brand copy and are editable by an Admin. | Must |
| FR-22 | Each service can link to matching gallery items. | Should |
| FR-23 | Each service has its own page or section anchor so it can be shared and indexed by search engines. | Should |

### 3.5 Gallery

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-24 | The gallery displays work as an image grid with lazy loading. | Must |
| FR-25 | Visitors can filter by category: Senator, Kaftan, Suit, Shirt, Trouser, Agbada, Women's Senator. | Must |
| FR-26 | Selecting an image opens a larger view (lightbox) with next and previous controls and a caption. | Must |
| FR-27 | Each lightbox view includes a "Order something like this" button that opens the enquiry form with the item referenced. | Should |
| FR-28 | An Admin can upload, caption, categorise, reorder, feature, and delete gallery items. | Must |
| FR-29 | Uploaded images are automatically resized and compressed into web-ready formats. | Should |

### 3.6 Consultation and Order Enquiry

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-30 | A consultation form collects: full name, phone number, email (optional), preferred contact method (WhatsApp, call, email), service of interest, preferred date and time, and a message. | Must |
| FR-31 | An order-enquiry form collects the same contact fields plus: garment type, occasion, event date or needed-by date, quantity, fabric or colour preference, and optional reference images (up to 5, each up to 5 MB). | Must |
| FR-32 | Forms validate input on the client and the server, with clear inline error messages. | Must |
| FR-33 | Phone numbers accept Nigerian formats (for example 080..., +234...) and international numbers. | Must |
| FR-34 | On submit, the visitor sees a confirmation message stating that the brand will respond, and receives no promise of a specific time unless the owner defines one. | Must |
| FR-35 | Each submission is stored in the database and emailed to the brand's enquiry address. | Must |
| FR-36 | A "Send via WhatsApp" option opens WhatsApp with a message pre-filled from the form data. | Should |
| FR-37 | Forms include spam protection (honeypot field and rate limiting, with CAPTCHA only if abuse appears). | Must |
| FR-38 | The consultation form states that measurements are taken during consultation and fitting, and does not ask for body measurements online in Release 1. | Should |
| FR-39 | Appointment availability and slot booking with calendar sync. | Could |

### 3.7 Garment Care and Laundry

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-40 | A dedicated page explains that the brand offers laundry services to help customers maintain their garments, using the approved copy. | Must |
| FR-41 | The page directs customers to contact the brand for availability, pricing, and enquiries, and provides WhatsApp, call, and email buttons. | Must |
| FR-42 | A laundry enquiry form collects name, phone, garment types, and message. | Should |
| FR-43 | Garment care tips (storage, washing, ironing of senator wear, kaftans, and suits) can be published as short articles. | Could |

### 3.8 Contact Page

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-44 | The page shows both phone numbers, the WhatsApp link, the email address, and the location (Enugu, Nigeria). | Must |
| FR-45 | The page embeds a map of the business location once the owner supplies the full address or a Google Maps link. | Should |
| FR-46 | The page shows opening hours once the owner supplies them. | Should |
| FR-47 | A general contact form collects name, phone or email, subject, and message. | Must |
| FR-48 | The page links to the brand's social media profiles once the owner supplies them. | Should |

### 3.9 Testimonials

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-49 | The site displays only genuine testimonials that the owner has approved. | Must |
| FR-50 | An Admin can add, edit, hide, and delete testimonials, including client name and optional photo. | Should |

### 3.10 Admin Area

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-51 | Admins sign in with email and password; the admin area is not reachable without authentication. | Must |
| FR-52 | Admins can manage gallery items (FR-28), services text (FR-21), and testimonials (FR-50). | Must |
| FR-53 | Admins can view, search, filter, and export enquiries, and mark each as New, Contacted, In Progress, Completed, or Closed. | Must |
| FR-54 | Admins can add internal notes to an enquiry. | Should |
| FR-55 | Admins can edit contact details, opening hours, and social links in one place, and the changes appear site-wide. | Should |
| FR-56 | Admin accounts support password reset by email. | Must |
| FR-57 | Two roles exist: Owner (full access, manages Admin accounts) and Staff (manages content and enquiries only). | Could |

### 3.11 Notifications and Tracking

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-58 | New enquiries trigger an email to the brand's enquiry address within 1 minute of submission. | Must |
| FR-59 | The site records clicks on WhatsApp, call, and email buttons and form submissions as analytics events. | Should |
| FR-60 | The visitor receives an auto-reply email confirming receipt when an email address is provided. | Could |

## 4. External Interface Requirements

The site talks to people through a responsive interface and to outside services through five defined integrations.

### 4.1 User Interfaces

- **UI-01:** Layouts are designed mobile-first and verified at 360 px, 768 px, 1024 px, and 1440 px widths.
- **UI-02:** Touch targets are at least 44 × 44 px, and body text is at least 16 px on mobile.
- **UI-03:** All pages share one consistent header, footer, colour system, and typography.
- **UI-04:** Primary actions (consultation, WhatsApp) stay visible without scrolling on mobile.
- **UI-05:** Error, loading, and empty states are designed for forms, gallery, and admin lists.

### 4.2 Hardware Interfaces

No direct hardware interfaces are required. Visitors use standard phones, tablets, and computers.

### 4.3 Software and Service Interfaces

| ID | Service | Purpose | Priority |
| --- | --- | --- | --- |
| IF-01 | WhatsApp click-to-chat (wa.me link) | Floating button, CTAs, pre-filled enquiry message | Must |
| IF-02 | Email delivery service (SMTP or transactional email provider) | Enquiry notifications, password resets, auto-replies | Must |
| IF-03 | Map embed (Google Maps or OpenStreetMap) | Location on the Contact page | Should |
| IF-04 | Web analytics (for example Google Analytics or a privacy-friendly alternative) | Traffic, conversions, button-click events | Should |
| IF-05 | Image storage and delivery (cloud storage or CDN) | Gallery and uploaded reference images | Must |

### 4.4 Communication Interfaces

- **CI-01:** All traffic uses HTTPS with TLS 1.2 or higher, and HTTP requests redirect to HTTPS.
- **CI-02:** Form submissions use JSON or form-encoded POST requests to the site's own server endpoints.
- **CI-03:** Email notifications use authenticated sending (SPF and DKIM) so they reach inboxes rather than spam.

## 5. Non-Functional Requirements

The site must load fast on mobile data, protect enquiry data, and be easy for non-technical staff to keep current. Each target below is testable before launch.

### 5.1 Performance

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-01 | Largest Contentful Paint on a mid-range phone over 4G | 2.5 s or less |
| NFR-02 | Lighthouse performance score (mobile) on Home, Services, and Gallery | 85 or higher |
| NFR-03 | Total page weight of the Home page on first load | 2 MB or less |
| NFR-04 | Gallery images served in modern formats (WebP or AVIF) with responsive sizes and lazy loading | All images |
| NFR-05 | Form submission response time under normal load | 2 s or less |

### 5.2 Security and Privacy

| ID | Requirement |
| --- | --- |
| NFR-06 | The admin area requires authentication, uses hashed passwords (bcrypt or Argon2), and locks or slows repeated failed sign-ins. |
| NFR-07 | Inputs are validated and sanitised on the server to prevent SQL injection and cross-site scripting; CSRF protection applies to state-changing requests. |
| NFR-08 | File uploads are limited by type (JPG, PNG, WebP) and size, and are scanned or re-encoded before storage. |
| NFR-09 | Customer data (names, phone numbers, emails, reference images) is collected only for responding to enquiries and is accessible only to Admins. |
| NFR-10 | A privacy policy page explains what data is collected and why, and the site complies with the Nigeria Data Protection Act 2023. Legal review is the owner's responsibility. |
| NFR-11 | A cookie notice appears if analytics or tracking cookies are used. |
| NFR-12 | Secrets and API keys are stored in environment variables, never in the code repository. |

### 5.3 Reliability and Availability

| ID | Requirement | Target |
| --- | --- | --- |
| NFR-13 | Monthly uptime of the public site | 99.5% or higher |
| NFR-14 | Automated database and media backups | Daily, with 14 days retained |
| NFR-15 | If email delivery fails, the enquiry is still saved and visible in the admin area | Always |

### 5.4 Usability and Accessibility

- **NFR-16:** A first-time visitor can find the WhatsApp or consultation button within 5 seconds on any page.
- **NFR-17:** The site meets WCAG 2.1 level AA for colour contrast, keyboard navigation, focus states, and alt text on all images.
- **NFR-18:** Text sizes and spacing remain readable when the browser zoom is 200%.

### 5.5 Search Engine Optimisation

- **NFR-19:** Every page has a unique title tag, meta description, and one H1.
- **NFR-20:** The site provides a sitemap.xml, robots.txt, canonical URLs, and clean readable page addresses (for example /services/senator-wear).
- **NFR-21:** LocalBusiness structured data (schema.org) describes the brand, Enugu location, phone, and services.
- **NFR-22:** Open Graph and Twitter card tags make shared links show a title and image.
- **NFR-23:** The site is registered with Google Search Console and a Google Business Profile is recommended for local search.

### 5.6 Compatibility

- **NFR-24:** The site works on the latest two major versions of Chrome, Safari, Firefox, Edge, and Samsung Internet.
- **NFR-25:** The site works on Android 9 and later, and iOS 14 and later.

### 5.7 Maintainability and Scalability

- **NFR-26:** Admins update content without developer help, after a one-hour handover session.
- **NFR-27:** The code is version-controlled, documented, and follows a consistent structure, with a README covering setup and deployment.
- **NFR-28:** The architecture allows later additions (online payments, a customer account area, a blog) without a rebuild.
- **NFR-29:** The gallery supports at least 500 items without noticeable slowdown.

## 6. Content and Data Requirements

The site stores six kinds of records and depends on content that the owner must supply before launch.

### 6.1 Data Entities

| Entity | Key fields | Used by |
| --- | --- | --- |
| Enquiry | ID, type (consultation, order, laundry, general), name, phone, email, preferred contact method, service, message, event or needed-by date, quantity, reference images, status, internal notes, created date | FR-30 to FR-42, FR-47, FR-53, FR-54 |
| Service | ID, title, slug, description, image, display order, visible flag | FR-19 to FR-23 |
| Gallery item | ID, image, caption, category, featured flag, display order, created date | FR-24 to FR-29 |
| Testimonial | ID, client name, quote, optional photo, visible flag | FR-12, FR-49, FR-50 |
| Admin user | ID, name, email, hashed password, role, last sign-in | FR-51, FR-56, FR-57 |
| Site settings | Phone numbers, WhatsApp link, email, address, map link, opening hours, social links | FR-03, FR-44 to FR-48, FR-55 |

### 6.2 Content Inventory

| Content item | Source | Status |
| --- | --- | --- |
| Brand name, motto, About, Vision, Mission, Values | Brand information document | Available |
| Service names and descriptions (8 services plus garment care) | Brand information document | Available; owner may expand |
| Contact details (2 phones, WhatsApp, email) | Brand information document | Available |
| Logo files (vector and PNG) | Owner | Needed |
| Photos of finished garments (at least 24 for launch, across categories) | Owner or photographer | Needed |
| Hero image and workshop or founder photos | Owner | Needed |
| Full address, map link, opening hours | Owner | Needed |
| Social media links | Owner | Needed |
| Testimonials with client permission | Owner | Needed |
| Bespoke process steps (FR-11) | Owner | Needed |
| Privacy policy and terms text | Owner with legal review | Needed |

### 6.3 Content Rules

- **CR-01:** All copy follows the brand voice: professional, confident, warm, and honest, in line with the Integrity value.
- **CR-02:** The site makes no claims the brand cannot support (for example delivery times, prices, or awards) unless the owner confirms them.
- **CR-03:** Client photos and testimonials are published only with the client's consent.
- **CR-04:** Every image has descriptive alt text and a caption where relevant.
- **CR-05:** The brand name is written GOODYEXCELLENT COUTURE in headings and branding, and the motto is shown exactly as supplied.

## 7. Design and Branding Guidelines

The design must feel premium, confident, and distinctly its own, so that a visitor judges the brand by the quality of its craft before reading a word. These are design directions, not fixed choices; the owner approves the final identity.

| Area | Direction |
| --- | --- |
| Overall feel | Refined and uncluttered, with generous white space and large, high-quality garment photography. |
| Colour | A restrained palette of 2 to 3 brand colours plus neutrals. The owner's logo colours decide the palette; a deep, rich primary with a gold or warm accent is one suitable option for a premium bespoke look. |
| Typography | An elegant serif for headings paired with a clean sans-serif for body text. Maximum two typefaces. |
| Imagery | Real photos of finished garments, details (stitching, finishing, fabric), and the workshop. Stock images are avoided on the Home and Gallery pages. |
| Tone of voice | Professional, confident, and warm, using the supplied motto and brand copy. |
| Interaction | Subtle transitions only. Motion must never slow down the page or hide content. |
| Calls to action | One clear primary action per screen: Book a Consultation, with WhatsApp as the always-available secondary action. |
| Trust cues | Testimonials, consistent contact details, visible location, and the six brand values. |

**Page-to-sitemap mapping:** the pages in Appendix A each reuse the same header, footer, and CTA components so the site reads as one brand.

## 8. Risks, Phasing and Acceptance Criteria

Release 1 launches the full brand site with lead capture and a simple admin area; payments and richer features wait for later releases. The main project risk is missing content, not code.

### 8.1 Release Plan

| Release | Scope | Requirements |
| --- | --- | --- |
| Release 1 (MVP) | Public pages, gallery, consultation and enquiry forms, WhatsApp and email notifications, admin area, SEO, analytics | All Must items, and Should items that fit the schedule |
| Release 2 | Appointment booking with calendar sync, auto-reply emails, staff roles, care-tips articles | FR-39, FR-57, FR-60, FR-43 |
| Release 3 | Online payment for deposits or ready-made items, customer accounts and order tracking, blog or lookbook | Future requirements, to be specified |

### 8.2 Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Owner does not supply enough quality photos | Weak gallery undermines the premium positioning | Agree a photo checklist early and arrange a short photo session of finished garments |
| Enquiries go unanswered | Lost customers and damage to the Reliability value | Immediate email alert, a status workflow in the admin area, and a documented response routine |
| Slow pages on mobile data | Visitors leave before the page loads | Enforce image optimisation and the NFR-01 to NFR-05 targets |
| Spam or fake submissions | Staff time wasted | Honeypot, rate limiting, and CAPTCHA if needed (FR-37) |
| Scope creep toward e-commerce | Delay and extra cost | Keep payments in Release 3 and agree changes through a change request |
| Content or testimonial published without consent | Privacy and trust issues | Apply CR-03 and keep consent records |

### 8.3 Acceptance Criteria

Release 1 is accepted when all of the following are true:

- Every Must requirement passes its test, and any Should requirement left out is listed and agreed.
- The Lighthouse mobile score is 85 or higher on Home, Services, and Gallery (NFR-02).
- A test enquiry from each form reaches the admin area and the enquiry email within 1 minute.
- WhatsApp, call, and email buttons open the correct number and address on Android and iOS phones.
- The site passes testing on the browsers and devices in NFR-24 and NFR-25.
- No critical or high security issues remain open after a basic security review.
- The owner approves the final design, copy, and images in writing.
- Staff complete the admin handover session and can add a gallery item and change an enquiry status unaided.

## 9. Appendices

### Appendix A: Sitemap

The public site has seven main pages plus legal and error pages, and the admin area sits behind a sign-in.

&#91;embedded content: sitemap · 7 main pages, 2 support pages, 1 admin area\]

Every public page shares the same header, footer, and WhatsApp button, and the Services and Gallery pages feed the enquiry form.

### Appendix B: Traceability from Brand Information to Requirements

| Brand information item | Where it appears on the site | Requirements |
| --- | --- | --- |
| Brand name, motto, positioning | Header, hero, footer, About | FR-01, FR-03, FR-07, FR-14 |
| About the Brand | About page | FR-14 |
| Vision and Mission | About page | FR-15 |
| Services A to H (senator wear to fashion consultations) | Services page, Home overview, Gallery categories | FR-08, FR-19 to FR-23, FR-25 |
| Garment Care and Laundry | Dedicated page and enquiry option | FR-40 to FR-43 |
| Brand values | Home and About | FR-10, FR-16 |
| Phone numbers, WhatsApp, email, location | Header, footer, Contact page, floating button | FR-03 to FR-05, FR-44 |
| Fashion consultations | Consultation form and booking | FR-30, FR-39 |
| Future ambition: training tailors and building a fashion institution | Not a Release 1 feature; may become a Careers or Academy page later | Release 3 candidate |

### Appendix C: Open Questions

| # | Question for the brand owner | Why it matters |
| --- | --- | --- |
| 1 | Is online payment needed at launch, or are orders agreed by enquiry first? | Release 1 scope assumes enquiry only (Section 1.2) |
| 2 | What is the full workshop address, and what are the opening hours? | Contact page, map, and local SEO (FR-45, FR-46) |
| 3 | Do you have a logo and brand colours, or should they be designed? | Visual identity and design start |
| 4 | What are your social media handles? | Footer and Contact links (FR-48) |
| 5 | Which domain name should be registered, and do you want a business email on it? | Hosting, email delivery, and brand trust |
| 6 | Should prices be shown, or shared only on enquiry? | Services page content and CR-02 |
| 7 | What typical production and delivery times can the site state? | Honest delivery promises (Reliability and Integrity values) |
| 8 | The About text says "abada" and the Services list says "agbada". Which spelling should the site use? | Consistent copy and search terms |
| 9 | Does the laundry service include pick-up and delivery, and is it open to the public? | Laundry page content (FR-40 to FR-42) |
| 10 | Who answers enquiries, and what response time can you commit to? | Confirmation message wording (FR-34) and the response routine |
| 11 | Should the site serve customers outside Nigeria, with international contact formats and shipping information? | Vision mentions customers beyond Nigeria; affects forms and content |
| 12 | Are women's outfits limited to senator wear, or will other styles be added? | Services and gallery categories (FR-19, FR-25) |

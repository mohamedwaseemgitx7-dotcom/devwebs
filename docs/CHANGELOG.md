# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com); versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added
- **FlashCart web** (`apps/flashcart-web`): React 19 + Vite + TypeScript + Tailwind storefront.
  - Product listing with URL-driven search, category/price/colour/rating/shipping/stock filters, sorting, pagination,
    skeleton loading, empty and error states; product details; favorites.
  - Guest cart (localStorage) merged into the server cart on sign-in; cart page with quantity controls and stock warnings.
  - Checkout with address validation, delivery speeds, per-attempt idempotency key, price/stock-change handling;
    order confirmation and order history.
  - Sign-in / sign-up with open-redirect-safe `next=`; in-memory access token, HttpOnly refresh cookie.
  - Admin: dashboard (revenue, orders, customers, low stock), product creation, price edits with optimistic-lock
    conflicts, stock adjustments, show/hide, order status changes.
  - Responsive layout (icon rail + bottom nav on mobile, filter drawer), skip link, Ctrl+K / `/` search shortcut,
    visible focus, ARIA labels.
  - 22 unit/component tests (Vitest) and 8 Playwright end-to-end tests on an isolated stack, with screenshots in
    `docs/screenshots/`.
- `scripts/ci/check-npm-age.py` supply-chain cooldown check + documented security exceptions.
- Graphify 0.9.83 code knowledge graph (local, code-only; `graphify-out/` gitignored).
- API: `active` field on product responses (admin visibility state).
- Docs: README progress tracker, PROJECT-STATUS, TROUBLESHOOTING (17 entries), DECISIONS (14 ADRs), INSTALLATION-LOG.

### Changed
- `users.token_version` renamed to `session_version` (clearer; removes Bandit false positives — TS-014).

### Fixed
- Guest-cart merge could double quantities when the page reloaded mid-request (TS-007).
- Filter sidebar remounted on every change, losing keyboard focus (TS-009).
- Admin row remount wiped the save confirmation (TS-010).
- Product cards not full-width on mobile (TS-016).

### Security
- Python dev deps: filelock 4.1.0 → 4.2.1 and certifi 2026.7.22 → 2026.10.19 (security-fix cooldown exceptions, TS-018).
- npm overrides for undici 8.12.2 and zod 4.6.6 (high-severity advisories in dev dependencies) — `npm audit`: 0.

## [0.1.0] — 2026-10-24
### Added
- FlashCart API (FastAPI + MongoDB): catalog, cart, favorites, transactional checkout with idempotency keys, orders,
  admin, signed webhooks, auth with refresh-token rotation, health/readiness/metrics, structured logging, rate limiting,
  security headers. 78 backend tests.
- Checksum-verified tool installer, local MongoDB replica-set scripts, project `CLAUDE.md`.

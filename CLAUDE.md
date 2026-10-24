# FlashCart + CloudOps Sentinel — project instructions

Read this file, then `docs/PROJECT-STATUS.md`, before doing any work in a new session.

## What this is
- **FlashCart** (`apps/flashcart-api` FastAPI + MongoDB, `apps/flashcart-web` React/Vite/TS): multi-user e-commerce.
- **CloudOps Sentinel** (`apps/sentinel*`, planned): monitoring/security dashboard that watches FlashCart.
- Reference material: `references/` (storefront screenshot, 40-page PDF → `references/PDF-INVENTORY.md`).

## Hard rules
- Budget ₹0. Never create billable cloud resources, run `terraform apply/destroy`, publish publicly or change
  IAM/network exposure without the owner's explicit approval for that specific action.
- Supabase is prohibited. Database = MongoDB Atlas M0 (hosted) / portable local mongod (dev/tests).
- Keep everything on D:. C: has little free space — caches go to `.cache/` (dot-source `scripts/setup/env.ps1`).
- Never commit, print or log secrets. `.env` files are gitignored; only `.env.example` with placeholders is committed.
  Never ask the owner to paste passwords/tokens into chat — use official login flows.
- Supply-chain cooldown: only adopt package/tool versions published ≥14 days ago (uv `exclude-newer`,
  pinned versions in `scripts/setup/install-tools.ps1`, checksums verified).
- Never weaken a test or skip a security check to get green. Fix the cause; record it in `docs/TROUBLESHOOTING.md`.
- Never claim something is deployed/verified without evidence (command output, URL check).

## Common commands (PowerShell, from repo root)
```powershell
. .\scripts\setup\env.ps1                 # put .tools\bin on PATH, caches on D:
.\scripts\dev\start-mongo.ps1             # local MongoDB replica set rs0 on 127.0.0.1:27017
cd apps\flashcart-api
uv run pytest -q                          # backend tests (needs local mongod)
uv run ruff check app tests; uv run bandit -r app -c pyproject.toml
uv run python -m app.seed                 # seed demo catalog
uv run uvicorn app.asgi:app --port 8000   # API at http://127.0.0.1:8000 (docs: /api/docs)
gitleaks dir . --config .gitleaks.toml --redact
```

## Conventions
- Money is integer paise (`price_paise`), currency INR. Server computes every total.
- All business rules (prices, stock, roles, ownership) are enforced server-side.
- Concept numbers like `#25` in comments refer to `docs/PDF-CONCEPT-MAPPING.md`.
- Update `docs/PROJECT-STATUS.md`, `docs/CHANGELOG.md`, `docs/DECISIONS.md`, `docs/TROUBLESHOOTING.md`,
  `docs/INSTALLATION-LOG.md` as work happens. Mark features: planned / in progress / done+verified / blocked.

# Installation Log

Everything installed for this project, where it lives, how it was verified and how to remove it.
**Nothing was installed system-wide**; no PATH, registry or service changes were made.

## Pre-existing tools (inspected 2026-10-24, not installed by this project)
Git 2.55.0 · Node 24.19.0 · npm 11.17.0 · Python 3.14.7 and 3.13.15 · uv 0.9.28 · GitHub CLI 2.97.0 ·
Vercel CLI 58.5.1 · WSL 2.5.9 (no distribution) · winget · choco.

## Project-local CLI tools — `scripts/setup/install-tools.ps1` → `.tools\` (D:)
| Tool | Version | Source | Verification | Result |
|---|---|---|---|---|
| Terraform | 1.16.5 | releases.hashicorp.com | SHA-256 vs `SHA256SUMS` | ✅ `Terraform v1.16.5` |
| Trivy | 0.75.0 | github.com/aquasecurity/trivy releases | SHA-256 vs `checksums.txt` | ✅ `Version: 0.75.0` |
| Gitleaks | 8.30.1 | github.com/gitleaks/gitleaks releases | SHA-256 vs `checksums.txt` | ✅ `8.30.1` |
| k6 | 2.3.0 | github.com/grafana/k6 releases | SHA-256 vs `checksums.txt` | ✅ `k6.exe v2.3.0` |
| Helm | 4.3.0 | get.helm.sh | SHA-256 vs `.sha256sum` | ✅ `v4.3.0` |
| kind | 0.33.0 | github.com/kubernetes-sigs/kind releases | SHA-256 vs `.sha256sum` | ✅ `kind v0.33.0` |
| kubectl | 1.37.1 | dl.k8s.io | SHA-256 vs `.sha256` | ✅ `Client Version: v1.37.1` |
| MongoDB Community | 8.0.34 | fastdl.mongodb.org | SHA-256 vs `.sha256` | ✅ `db version v8.0.34` |

Versions follow the 14-day cooldown (ADR-004); newer releases of Trivy (0.76.1) and Helm (4.3.1) were skipped.
**Remove:** `Remove-Item -Recurse .tools` (stop mongod first: `scripts\dev\stop-mongo.ps1`).

## Python environments (uv, cache in `.cache\uv`)
| Env | Purpose | Key packages |
|---|---|---|
| `apps/flashcart-api/.venv` | API + tests | fastapi 0.143.0, pymongo 4.18.3, pydantic 2.14.0, argon2-cffi 25.1.0, pyjwt 2.15.1, mangum 0.22.0, pytest 9.1.1, ruff, bandit, pip-audit |
| `.tools-venv` | PDF rendering | pymupdf |
Resolution limited by `exclude-newer = 2026-10-10`. **Remove:** delete the `.venv` folders.

## Node packages (`apps/flashcart-web`, cache in `.cache\npm`)
react 19.3.0, react-router 7.18.4, @tanstack/react-query 5.104.1, vite 8.3.4, tailwindcss 4.3.3, typescript 6.0.3,
vitest 5.0.3, @playwright/test 1.64.0, eslint 10.12.0 (full list: `package-lock.json`). Security overrides:
undici 8.12.2, zod 4.6.6 (TS-004). **Remove:** delete `node_modules`.

## Playwright browsers
Chromium 1248 + headless shell, FFmpeg — installed to `.cache\ms-playwright` via `PLAYWRIGHT_BROWSERS_PATH`
(default would have been on C:). **Remove:** delete that folder.

## Docker Desktop — ⛔ not installed
Installer 4.96.3 downloaded to `.tools\downloads` (Authenticode: valid, Docker Inc). Planned flags:
`--installation-dir=D:\Docker\DockerDesktop --wsl-default-data-root=D:\Docker\wsl`. UAC prompt was cancelled (TS-002).

## Skills / plugins researched (identity verified via GitHub API, none installed yet)
| Requested name | Canonical repo | License | Relevance / plan |
|---|---|---|---|
| NVIDIA Skillspector | NVIDIA/SkillSpector | Apache-2.0 | High — scan any skill before installing it |
| Graphify | Graphify-Labs/graphify (moved from safishamsi) | Apache-2.0 | Medium — knowledge graph; Mermaid fallback meanwhile |
| Impeccable | pbakaus/impeccable | Apache-2.0 | Medium — UI polish audit |
| Taste | Leonxlnx/taste-skill | MIT | Low — overlaps Impeccable |
| awesome-design-md | VoltAgent/awesome-design-md | MIT | Reference only |
| Playwright CLI | microsoft/playwright-cli | Apache-2.0 | Low — `@playwright/test` already covers e2e |
| Headroom | headroomlabs-ai/headroom (moved from chopratejas) | Apache-2.0 | Not installing — proxies LLM traffic |
| Ponytail | DietrichGebert/ponytail | MIT | Not installing — adds global lifecycle hooks |
| img2threejs | img2threejs/img2threejs | Apache-2.0 | Not relevant (no 3D) |
| Screenshot-to-code | abi/screenshot-to-code | MIT | Not needed — UI built directly from the reference |

# External Integrations

**Analysis Date:** 2026-04-20

## APIs & External Services

**AI / LLM:**
- Anthropic Claude API — Tier-3 fallback for recipe extraction when `recipe-scrapers` fails or the page is an SPA
  - SDK/Client: `anthropic` (Python SDK), instantiated in `backend/scraper.py:308`
  - Model: `claude-sonnet-4-20250514` (constant `CLAUDE_MODEL` at `backend/scraper.py:43`)
  - `max_tokens`: 4096 (`CLAUDE_MAX_TOKENS`, `backend/scraper.py:44`) — raised from the initial 1024 after truncation incidents
  - Input cap: 20000 chars of page text (`CLAUDE_INPUT_CHAR_LIMIT`, `backend/scraper.py:45`)
  - Auth: `ANTHROPIC_API_KEY` env var, checked at `backend/scraper.py:304-306`
  - Stop-reason guard: `message.stop_reason == "max_tokens"` raises `ClaudeExtractError` at `backend/scraper.py:318-322`

**Recipe Source Websites (outgoing HTTP):**
- `recipe-scrapers` library's `scrape_me(url)` — makes its own HTTP request with its own User-Agent; used as Tier-1 path in `backend/scraper.py:122-130` (runs in a thread via `asyncio.to_thread` so it doesn't block the event loop)
- `httpx.AsyncClient` — Tier-2 fetch when `scrape_me` fails; configured with full Chrome-style `BROWSER_HEADERS`, HTTP/2, redirect-follow, 15 s timeout (`backend/scraper.py:110-119`)
- Known friction: sites behind Akamai/Cloudflare bot detection (AllRecipes) may 403 the `httpx` client due to TLS fingerprint, even though `scrape_me` succeeds

## Data Storage

**Databases:**
- SQLite
  - Connection: `DATABASE_URL` env var (defaults to `./recipes.db`)
  - Client: `sqlite-utils.Database` singleton in `backend/db.py:9-65`
  - PRAGMAs set on first open: `foreign_keys = ON`, `journal_mode = WAL` (`backend/db.py:18-19`)
  - Tables created lazily on first `get_db()` call if absent: `recipes`, `ingredients`, `steps`
  - Local artifacts present: `recipes.db`, `recipes.db-wal`, `recipes.db-shm` (all gitignored via `.gitignore`)

**File Storage:**
- Local filesystem only — SQLite file on disk; no S3/GCS/blob storage
- On Render, production path is `/data/recipes.db` via mounted persistent disk

**Caching:**
- None

## Authentication & Identity

**Auth Provider:**
- None — personal single-user app, no user accounts or login
  - No auth middleware in `backend/main.py`
  - CORS is open to `http://localhost:5173` only (`backend/main.py:19-25`)

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- uvicorn default stdout logging only; no structured logging library configured

## CI/CD & Deployment

**Hosting:**
- Render — single web service with persistent disk (`render.yaml` documented in `CLAUDE.md` but file not yet committed)

**CI Pipeline:**
- None configured (no `.github/workflows/`, no `.gitlab-ci.yml`)

## Environment Configuration

**Required env vars:**
- `DATABASE_URL` — SQLite path (required in prod, defaulted in dev)
- `ANTHROPIC_API_KEY` — required only when Tier-3 Claude fallback triggers
- `VITE_API_URL` — frontend build-time var (empty string in production)

**Secrets location:**
- `.env` file at project root (gitignored; exists but must not be read)
- `.env.example` committed as template
- On Render: set in the dashboard, not in a committed file

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None (no webhook emission; external calls are synchronous request/response only)

---

*Integration audit: 2026-04-20*

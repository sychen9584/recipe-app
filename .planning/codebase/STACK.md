# Technology Stack

**Analysis Date:** 2026-04-20

## Languages

**Primary:**
- Python >=3.11 — all backend code under `backend/` (`backend/main.py`, `backend/db.py`, `backend/scraper.py`)

**Secondary:**
- JavaScript/JSX — planned React frontend (not yet scaffolded; `frontend/` directory does not exist)
- SQL (implicit) — via `sqlite-utils` table DDL in `backend/db.py`

## Runtime

**Environment:**
- CPython 3.11+ (pinned by `requires-python = ">=3.11"` in `pyproject.toml`)
- ASGI via `uvicorn[standard]` — run with `uv run uvicorn backend.main:app --reload --port 8000`

**Package Manager:**
- `uv` (required — `pip` and direct `python` calls are forbidden per `AGENTS.md` and `CLAUDE.md`)
- Lockfile: `uv.lock` present (212KB, committed)
- Virtualenv: `.venv/` managed by `uv` (gitignored)

## Frameworks

**Core:**
- `fastapi` — HTTP framework, mounted in `backend/main.py:17` (`app = FastAPI(title="Recipe App")`)
- `uvicorn[standard]` — ASGI server
- `sqlite-utils` — thin DB wrapper used in `backend/db.py` for table creation and row insertion
- `pydantic` — bundled with FastAPI; `UrlIn(BaseModel)` in `backend/main.py:28`

**Testing:**
- Python stdlib `unittest` — all tests in `tests/test_scraper.py` use `unittest.TestCase`
- `fastapi.testclient.TestClient` — used for endpoint tests in `tests/test_scraper.py:105`

**Build/Dev:**
- `uv` for dependency resolution and venv management
- `python-dotenv` — loads `.env` at process start in `backend/main.py:1-3`

## Key Dependencies

**Critical:**
- `fastapi` — API surface
- `httpx` — async HTTP client with HTTP/2 for URL fetch in `backend/scraper.py:111`
- `h2 >=4.3.0` — enables HTTP/2 support inside `httpx`
- `brotli >=1.2.0` — decodes Brotli-compressed responses (required by Budget Bytes, many modern CDNs)
- `beautifulsoup4` — HTML parsing for Claude fallback text extraction (`backend/scraper.py:9`, `269-296`)
- `recipe-scrapers >=15.11.0` — Tier-1/Tier-2 recipe extraction; provides both `scrape_me` (auto-fetch) and `scrape_html` (BYO HTML) paths used in `backend/scraper.py:122-141`
- `anthropic` — Claude SDK for Tier-3 Claude fallback extraction in `backend/scraper.py:303-334`

**Infrastructure:**
- `sqlite-utils` — SQLite access with foreign-key + WAL PRAGMAs enabled in `backend/db.py:18-19`
- `python-multipart` — multipart body parser; required by FastAPI `UploadFile` used in `backend/main.py:87`
- `pint` — declared for future unit conversion in the scaler (not yet imported)
- `python-dotenv` — `.env` loading

## Configuration

**Environment:**
- Loaded by `load_dotenv()` at import time (`backend/main.py:1-3`)
- Key env vars (see `.env.example`):
  - `DATABASE_URL` — SQLite path; defaults to `./recipes.db` (local) / `/data/recipes.db` (Render)
  - `ANTHROPIC_API_KEY` — required for Claude Tier-3 fallback
  - `VITE_API_URL` — frontend-only; empty in production
- `.env` is present at project root and gitignored; do not read or quote it
- Paths must **never** be hardcoded — always `os.getenv("DATABASE_URL", "./recipes.db")` (enforced by `CLAUDE.md` and `AGENTS.md`)

**Build:**
- `pyproject.toml` — single manifest for all Python metadata + dependencies
- No `setup.py`, no `requirements.txt` — `uv` manages `uv.lock`
- No linter or formatter configs present (`.eslintrc`, `.prettierrc`, `ruff.toml`, `.flake8` — none)

## Platform Requirements

**Development:**
- Linux / WSL2 (dev has been on `Linux 6.6.87.2-microsoft-standard-WSL2`)
- `uv` installed globally (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- Node.js will be required once frontend is scaffolded (not yet)

**Production:**
- Render single web service (see `render.yaml` reference in `CLAUDE.md` — not yet committed)
- Persistent disk mounted at `/data` for SQLite database
- Build: `pip install uv && uv sync && cd frontend && npm i && npm run build`
- Start: `uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT`

---

*Stack analysis: 2026-04-20*

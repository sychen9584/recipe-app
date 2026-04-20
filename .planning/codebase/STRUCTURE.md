# Codebase Structure

**Analysis Date:** 2026-04-20

## Directory Layout

```
recipe-app/
├── backend/                  # All Python backend code
│   ├── __pycache__/          # (gitignored)
│   ├── db.py                 # SQLite singleton + schema DDL
│   ├── main.py               # FastAPI app + routes
│   └── scraper.py            # URL ingestion: 3-tier extraction cascade
├── tests/                    # unittest-based test suite
│   ├── __pycache__/          # (gitignored)
│   └── test_scraper.py       # Scraper + ingest endpoint tests
├── .planning/                # GSD planning directory (this folder)
│   └── codebase/             # Codebase reference docs
├── .claude/
│   └── settings.local.json   # Local Claude Code permissions
├── .venv/                    # uv-managed virtualenv (gitignored)
├── AGENTS.md                 # Agent-facing project brief
├── CLAUDE.md                 # Claude-facing project context and build order
├── pyproject.toml            # Python dependencies + metadata
├── uv.lock                   # Lockfile for reproducible installs
├── .env                      # Local secrets (gitignored; never read)
├── .env.example              # Env var template (committed)
├── .gitignore
├── recipes.db                # Dev SQLite database (gitignored)
├── recipes.db-shm            # WAL shared-memory file (gitignored)
└── recipes.db-wal            # WAL file (gitignored)
```

**Not yet created (referenced in `AGENTS.md` / `CLAUDE.md`):**
- `backend/parser.py` — Phase 3 photo + PDF ingestion via Claude Vision
- `backend/scaler.py` — Phase 4 serving-size scaler with Pint
- `frontend/` — Phase 5 React + Vite SPA (`src/App.jsx`, `RecipeList.jsx`, `RecipeDetail.jsx`, `AddRecipe.jsx`, `vite.config.js`, `package.json`)
- `render.yaml` — Phase 6 Render deploy config

## Directory Purposes

**`backend/`:**
- Purpose: All server-side Python code — one file per concern (API, DB, scraper)
- Contains: `.py` modules; no sub-packages
- Key files: `main.py` (entrypoint), `db.py` (persistence), `scraper.py` (URL ingestion)

**`tests/`:**
- Purpose: Unit + endpoint tests
- Contains: `test_*.py` modules using `unittest.TestCase`
- Key files: `test_scraper.py`

**`.planning/codebase/`:**
- Purpose: Reference docs consumed by `/gsd-plan-phase` and `/gsd-execute-phase`
- Contains: `STACK.md`, `ARCHITECTURE.md`, `STRUCTURE.md`, `CONVENTIONS.md`, `TESTING.md`, `INTEGRATIONS.md`, `CONCERNS.md`
- Generated: Yes (by `/gsd-map-codebase`)
- Committed: Yes

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI `app` instance; uvicorn target `backend.main:app`

**Configuration:**
- `pyproject.toml`: Python deps, version, Python floor
- `uv.lock`: Resolved dep versions
- `.env.example`: Env var template
- `.gitignore`: Standard Python + SQLite + frontend ignores

**Core Logic:**
- `backend/scraper.py`: `scrape_url(url)` is the public entry into the 3-tier extraction cascade
- `backend/db.py`: `get_db()` is the single way to obtain the DB handle
- `backend/main.py`: Route handlers orchestrate scraper + DB

**Testing:**
- `tests/test_scraper.py`: Unit tests for normalisers + endpoint smoke test
- No `conftest.py`, no `pytest.ini` — tests run via `unittest`

**Documentation:**
- `CLAUDE.md`: Project overview, build order, conventions (consumed by Claude Code)
- `AGENTS.md`: Same but shorter, for generic agent tools

## Naming Conventions

**Files:**
- Backend modules: lowercase, single-word (`main.py`, `db.py`, `scraper.py`)
- Tests: `test_<module>.py` mirroring the module under test
- Documentation: `UPPERCASE.md` at project root

**Directories:**
- Lowercase, singular or standard names (`backend/`, `tests/`, `frontend/`)

**Functions:**
- Public API: `snake_case` (`scrape_url`, `get_db`)
- Private helpers: leading underscore (`_fetch`, `_normalise_scraper`, `_parse_quantity`, `_try_scrape_me`)
- Constants: `UPPER_SNAKE_CASE` (`BROWSER_HEADERS`, `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `_INGREDIENT_RE`, `_UNICODE_FRACTIONS`)

**Pydantic models:** `PascalCase` with suffix denoting direction — `UrlIn` for request bodies (`backend/main.py:28`).

## Where to Add New Code

**New backend feature (photo/PDF parser, scaler, etc.):**
- Primary code: `backend/<feature>.py` — keep the flat layout (`backend/parser.py`, `backend/scaler.py`)
- Wire into routes by importing into `backend/main.py` and adding handlers there
- Tests: `tests/test_<feature>.py`

**New API route:**
- Add to `backend/main.py` under the `/api/` prefix
- Keep the static-files mount (`main.py:96-99`) as the **last** statement in the module — it catches `/*` and will shadow later routes
- Validate inputs with a Pydantic model defined at module scope alongside `UrlIn`

**New database table or column:**
- Extend `backend/db.py` — add the `if "<name>" not in db.table_names(): db["<name>"].create(...)` block inside `get_db()`
- Keep FKs explicit (`foreign_keys=[("recipe_id", "recipes", "id")]`)
- Remember: FK enforcement is ON, so always delete children before parents

**New frontend component (once scaffolded):**
- Implementation: `frontend/src/<Component>.jsx`
- Calls API via `${import.meta.env.VITE_API_URL}/api/...` (same-origin empty-string default)

**Shared helpers:**
- Currently there is no `backend/utils.py` — add one only when the same helper is imported by two backend modules. Don't pre-emptively abstract.

## Special Directories

**`.venv/`:**
- Purpose: uv-managed virtualenv
- Generated: Yes (by `uv sync`)
- Committed: No (gitignored)

**`.planning/`:**
- Purpose: GSD state, phase plans, codebase docs
- Generated: Yes (by GSD commands)
- Committed: Yes

**`frontend/dist/` (future):**
- Purpose: Vite build output, served as static files by FastAPI at `/`
- Generated: Yes (by `npm run build`)
- Committed: No (gitignored)

**`/data` (Render-only):**
- Purpose: Persistent disk mount; production SQLite lives at `/data/recipes.db`
- Generated: No — provisioned by Render
- Committed: N/A

---

*Structure analysis: 2026-04-20*

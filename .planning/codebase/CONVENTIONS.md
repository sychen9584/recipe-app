# Coding Conventions

**Analysis Date:** 2026-04-20

## Naming Patterns

**Files:**
- Backend modules: lowercase, short, single-word (`main.py`, `db.py`, `scraper.py`)
- Test files: `test_<module>.py` mirroring the module under test

**Functions:**
- Public: `snake_case` (`scrape_url`, `get_db`)
- Private helpers: leading underscore `_snake_case` (`_fetch`, `_normalise_scraper`, `_parse_ingredient_string`, `_split_name_prep`, `_parse_quantity`, `_try_scrape_me`, `_try_recipe_scrapers_html`)
- Async: `async def` only where it's actually useful (I/O waits) — `scrape_url`, `_fetch`, `_try_scrape_me`, `ingest_url`. Sync helpers stay sync; blocking library calls use `asyncio.to_thread` (see `backend/scraper.py:125`).

**Variables:**
- `snake_case` for locals and module-level data
- Module constants: `UPPER_SNAKE_CASE` (`BROWSER_HEADERS`, `CLAUDE_MODEL`, `CLAUDE_MAX_TOKENS`, `CLAUDE_INPUT_CHAR_LIMIT`, `CLAUDE_PROMPT`)
- Internal constants (not exported): leading underscore + UPPER_SNAKE (`_UNICODE_FRACTIONS`, `_QTY_PATTERN`, `_UNIT_PATTERN`, `_INGREDIENT_RE`, `_SCRAPER_RECOVERABLE`, `_FRAC_CHARS`)

**Types:**
- Pydantic request models: `PascalCase` with `In` suffix — `UrlIn(BaseModel)` (`backend/main.py:28`)
- Custom exceptions: `PascalCase` + `Error` suffix — `ClaudeExtractError` (`backend/scraper.py:299`)
- Type hints use modern Python 3.11+ syntax: `dict | None`, `list[str]`, `sqlite_utils.Database | None` (no `Optional[]` / `Union[]` / `List[]`)

## Code Style

**Formatting:**
- No formatter config committed (`ruff`, `black`, `isort` — none present)
- Code is hand-formatted but consistent: 4-space indent, double quotes for strings, trailing commas in multi-line function calls and data literals
- Long strings wrapped with parens + implicit concatenation (see `BROWSER_HEADERS` in `backend/scraper.py:20-24` and `CLAUDE_PROMPT` triple-quoted at `backend/scraper.py:47`)
- Section dividers for long files: `# ─────────────────────────────────────` (`backend/scraper.py:264`, `390`)

**Linting:**
- No linter configured. Type hints are consistent but not enforced by a checker.

## Import Organization

**Order** (observed in `backend/scraper.py:1-17` and `backend/main.py:1-15`):
1. Standard library (`os`, `json`, `re`, `asyncio`, `typing`)
2. Blank line
3. Third-party (`httpx`, `fastapi`, `anthropic`, `bs4`, `recipe_scrapers`, `pydantic`)
4. Blank line
5. Local (`from backend.db import get_db`, `from backend.scraper import scrape_url`)

**Dotenv loading:** `backend/main.py:1-3` calls `load_dotenv()` **before** importing any local module that might read env vars — this ordering is load-bearing; preserve it.

**Path Aliases:** None — always use full `backend.<module>` paths (`from backend.db import get_db`). The project is run from the repo root so this works with `uv run uvicorn backend.main:app`.

## Error Handling

**Patterns:**
- **Pipeline-style fallback:** tried paths return `None` on recoverable failure; only the last resort raises. See `scrape_url` in `backend/scraper.py:80-107`.
- **Recoverable-exception tuples** for catching families of library errors: `_SCRAPER_RECOVERABLE` at `backend/scraper.py:71-77` groups the five recipe-scrapers per-field exceptions.
- **Defensive `_safe` wrapper** for untrusted third-party methods: `_safe(fn, default)` at `backend/scraper.py:170-177` calls the method and returns `default` on *any* exception. Use this pattern whenever calling `recipe-scrapers` scraper attributes.
- **Custom exception carries context:** `ClaudeExtractError` messages always name the failure mode (missing key, API error, truncation, JSON parse). Never raise bare `Exception` with a generic message.
- **Translate at the boundary:** route handlers catch scraper `ValueError` / `httpx` errors and map to specific HTTP codes — `422` for source/fetch/parse issues, `500` for DB errors (`backend/main.py:48-78`). Internal code never uses `HTTPException`; that is handler-layer only.
- **Re-raise with chaining:** use `raise ... from e` to preserve the cause chain (`backend/scraper.py:103, 316, 334`).

## Logging

**Framework:** None. uvicorn's default access log goes to stdout.

**Patterns:**
- No `logging.getLogger(...)` calls anywhere
- Do not add `print()` for debug output — rely on exception messages surfacing through the FastAPI response

## Comments

**When to Comment:**
- Docstrings on public functions and non-obvious private helpers — one-line or short triple-quoted (`scrape_url`, `_try_scrape_me`, `_resolve_cook_time`, `_parse_ingredient_string`, `_split_name_prep`, `_page_text_for_claude`). Use them to explain *why* or the edge case, not what the code does.
- Inline `#` comments only for genuinely surprising mechanics (e.g. `backend/scraper.py:150` — "Avoid saving a title-only metadata hit as a recipe")
- Section dividers (box-drawing `─`) to break up long modules

**What NOT to do:**
- No TODO/FIXME/HACK/XXX comments exist in the codebase — do not introduce them; file a GSD task or CONCERNS entry instead
- Don't document obvious behaviour (`# increment counter`)

**Docstrings:** Plain English, no Sphinx/Google/Numpy format — typical pattern is one sentence plus a short follow-up clause.

## Function Design

**Size:** Helpers are small (<30 lines). `scrape_url` is the longest public function at ~27 lines and reads top-to-bottom as three fallback attempts. If a helper grows past ~40 lines, split it.

**Parameters:** Positional for required data (`scrape_url(url)`), keyword-only via type hints is not used. Type hints on every parameter and return in `backend/scraper.py`; `backend/db.py` uses them sparingly.

**Return Values:**
- `dict | None` pattern for "try this, return None if it didn't work" helpers (`_try_scrape_me`, `_try_recipe_scrapers_html`, `_normalise_scraper`)
- Tuples for structured splits — `_split_name_prep` returns `tuple[str, str]`
- Never return dicts with mixed shapes — all normalisers produce the same `{title, source_url, ...}` keys

## Module Design

**Exports:** No `__all__` declarations. Anything with a leading underscore is private by convention; callers should only import non-underscored names.

**Barrel Files:** None. No `backend/__init__.py` with re-exports — imports are always from the concrete module (`from backend.scraper import scrape_url`).

**Module size:** `backend/scraper.py` at 492 lines is on the upper end for this project. New unrelated features (photo parsing, scaling) should go in their own modules (`backend/parser.py`, `backend/scaler.py`) rather than accumulating in `scraper.py`.

---

*Convention analysis: 2026-04-20*

# Architecture

**Analysis Date:** 2026-04-20

## Pattern Overview

**Overall:** Single-service monolith — FastAPI backend that will also serve the built React SPA from `frontend/dist/` in production.

**Key Characteristics:**
- Flat module layout — no sub-packages inside `backend/`; each file is one responsibility (API, DB, scraper)
- Lazy singleton for DB — `backend/db.py` caches a `sqlite_utils.Database` instance in module-global `_db` and creates tables on first access
- Three-tier extraction pipeline for URL ingestion — `recipe-scrapers.scrape_me` → `scrape_html` with browser-header fetch → Claude LLM fallback
- Async at the edges — `POST /api/recipes/url` is `async def` and awaits the scraper; the DB layer is sync (`sqlite-utils` is blocking, which is fine because SQLite calls are fast)
- API-first routing — all JSON endpoints live under `/api/*`; static SPA mount is last so it never shadows API routes

## Layers

**API layer (`backend/main.py`):**
- Purpose: HTTP surface, request validation, error-to-status mapping, DB persistence orchestration
- Location: `backend/main.py`
- Contains: FastAPI app, CORS middleware, `UrlIn` Pydantic model, 5 route handlers, static-files mount
- Depends on: `backend/db.py` (for `get_db`), `backend/scraper.py` (for `scrape_url`)
- Used by: uvicorn ASGI server

**Ingestion layer (`backend/scraper.py`):**
- Purpose: Given a URL, return a normalised recipe dict — regardless of whether the site is supported by `recipe-scrapers`, returns proper schema.org JSON-LD, is an SPA, or requires LLM extraction
- Location: `backend/scraper.py`
- Contains: three-tier extraction cascade, HTML fetcher, Claude client wrapper, ingredient-string parser, quantity/yield/tag normalisers
- Depends on: `httpx`, `beautifulsoup4`, `recipe-scrapers`, `anthropic`
- Used by: `backend/main.py:47` via `await scrape_url(url)`

**Persistence layer (`backend/db.py`):**
- Purpose: Provide a ready-to-use `sqlite_utils.Database` with schema applied and PRAGMAs set
- Location: `backend/db.py`
- Contains: `get_db()` singleton factory, schema DDL for `recipes`/`ingredients`/`steps`
- Depends on: `sqlite-utils`
- Used by: `backend/main.py:14`, tests via `backend.db._db` reset pattern

## Data Flow

**URL ingestion (the only flow currently wired end-to-end):**

1. Client POSTs `{"url": "..."}` to `/api/recipes/url`
2. Pydantic `UrlIn(BaseModel)` validates it as `HttpUrl` (`backend/main.py:28-29`)
3. `scrape_url(url)` is awaited (`backend/main.py:47`)
4. **Tier 1:** `_try_scrape_me(url)` runs `recipe_scrapers.scrape_me` in a worker thread via `asyncio.to_thread` (`backend/scraper.py:122-130`). If it returns title+ingredients+steps → normalised via `_normalise_scraper`, tagged `source: "recipe-scrapers"`, returned
5. **Tier 2:** `_fetch(url)` uses `httpx.AsyncClient` with `BROWSER_HEADERS` + HTTP/2 to pull raw HTML (`backend/scraper.py:110-119`). That HTML is passed to `_try_recipe_scrapers_html(html, url)` which runs `scrape_html(..., supported_only=False)` for generic schema.org matching
6. **Tier 3:** Still-fetched HTML goes through `BeautifulSoup`; `_page_text_for_claude` harvests `<script type="application/json">` blobs (critical for Next.js/`__NEXT_DATA__` SPAs) *before* stripping scripts, then assembles visible text up to 20000 chars. `_claude_extract` calls Claude, parses JSON, `_normalise_claude` shapes it to the internal schema. Tagged `source: "claude"`
7. Errors are funnelled into `ValueError` and mapped to HTTP 422 at the handler
8. Handler inserts one row into `recipes`, then bulk-inserts `ingredients` and `steps` with `recipe_id` FK (`backend/main.py:55-76`)
9. Response is `201 Created` with full recipe JSON including the injected `id` and `source` tag

**State Management:**
- Server-side: SQLite only, accessed via the lazy singleton `get_db()`
- No in-memory caches, no session state, no queues

## Key Abstractions

**Three-tier extraction cascade:**
- Purpose: Maximise recipe coverage while minimising Claude API spend
- Examples: `backend/scraper.py:80-107` (`scrape_url`)
- Pattern: Each tier returns `dict | None`; falling through to the next tier is silent unless the last tier raises. The returned dict carries a `source` field so the caller and UI know which path succeeded.

**Normalised recipe dict (internal schema):**
- Purpose: Uniform shape across all extraction sources, matches DB columns
- Shape: `{title, source_url, servings, prep_min, cook_min, cuisine, tags, ingredients, steps, source}`
- Produced by: `_normalise_scraper` (`backend/scraper.py:144-167`) for tiers 1/2, `_normalise_claude` (`backend/scraper.py:337-387`) for tier 3
- Consumed by: `backend/main.py:55-76` for DB persistence

**Ingredient string parser:**
- Purpose: Turn free-text lines like `"1 ½ cups flour, sifted"` into `{quantity: 1.5, unit: "cups", name: "flour", preparation: "sifted"}`
- Location: `_INGREDIENT_RE` (`backend/scraper.py:417-426`), `_parse_ingredient_string`, `_split_name_prep`, `_parse_quantity`
- Pattern: single compiled regex with optional `qty`/`unit` named groups; on non-match the whole line becomes `name`; unicode fractions (`½ ⅓ ¼`…) decoded via `_UNICODE_FRACTIONS` table; commas inside `()` don't split preparation

**Lazy DB singleton:**
- Purpose: Create tables exactly once, reuse the connection
- Location: `backend/db.py:9-65`
- Pattern: Module-global `_db` guarded by `is not None` check; tests reset via `backend.db._db = None` (see `tests/test_scraper.py:113, 148, 159`)

## Entry Points

**HTTP server:**
- Location: `backend/main.py:17` (`app = FastAPI(...)`)
- Triggers: uvicorn launched via `uv run uvicorn backend.main:app --reload --port 8000`
- Responsibilities: All JSON API routes + future SPA mount

**Routes (all defined in `backend/main.py`):**
- `GET  /api/recipes` — stub, returns `[]` (`main.py:32-34`)
- `GET  /api/recipes/{recipe_id}` — stub, 404 (`main.py:37-39`)
- `POST /api/recipes/url` — **implemented**, full ingestion path (`main.py:42-83`)
- `POST /api/recipes/upload` — stub, returns `{"status": "not implemented"}` (`main.py:86-88`)
- `DELETE /api/recipes/{recipe_id}` — stub (`main.py:91-93`)
- Static mount `/` → `frontend/dist` — wrapped in `try/except RuntimeError` so the server starts even before the frontend is built (`main.py:96-99`)

## Error Handling

**Strategy:** Translate domain/infrastructure exceptions into appropriate HTTP status codes at the route handler; never let raw stack traces leak.

**Patterns:**
- Scraper raises `ValueError` for recoverable parse failures; `httpx.HTTPStatusError` / `httpx.HTTPError` for fetch failures — handler maps all three to HTTP 422 (`backend/main.py:48-53`)
- DB errors → HTTP 500 via bare-`Exception` catch (`backend/main.py:77-78`) — coarse but acceptable at this stage
- Inside the scraper, `ClaudeExtractError` carries a human-readable reason (API key missing, call failed, truncated response, JSON parse failed) — surfaced through `ValueError(f"Claude fallback failed: {e}")`
- `recipe-scrapers` per-field exceptions are caught via `_SCRAPER_RECOVERABLE` tuple (`backend/scraper.py:71-77`) — field-level failures don't abort extraction

## Cross-Cutting Concerns

**Logging:** uvicorn default stdout only. No logger configured anywhere in `backend/`.

**Validation:** Pydantic on inputs (`UrlIn` with `HttpUrl`); defensive coercion on outputs via `_int_or_zero`, `_clean_text`, `_string_list`, `_parse_yield` in `backend/scraper.py:170-261`.

**Authentication:** None — personal single-user app.

**CORS:** Development-only origin `http://localhost:5173` allowed in `backend/main.py:19-25`.

---

*Architecture analysis: 2026-04-20*

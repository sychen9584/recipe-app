# Codebase Concerns

**Analysis Date:** 2026-04-20

## Tech Debt

**Stub route handlers:**
- Issue: Four of five API routes are placeholders returning static data
- Files: `backend/main.py:32-34` (`list_recipes` returns `[]`), `:37-39` (`get_recipe` always 404s), `:86-88` (`ingest_upload` returns "not implemented"), `:91-93` (`delete_recipe` returns "not implemented")
- Impact: The DB has a `recipes` table schema but nothing reads from it — recipes ingested via `POST /api/recipes/url` are invisible to the UI
- Fix approach: Implement `list_recipes` / `get_recipe` next (both are trivial `sqlite-utils` queries) before building the frontend

**`ingredients` rows store raw `unit` strings with no normalisation:**
- Issue: `_parse_ingredient_string` writes whatever unit token it saw (`cups`, `cup`, `c.`, `tbsp`, `tablespoons`) without canonicalising to a single form
- Files: `backend/scraper.py:440` (`unit = (match.group("unit") or "").lower()`)
- Impact: The planned scaler (`backend/scaler.py`, Phase 4) will need to handle every alias when doing Pint conversion, and `SELECT DISTINCT unit FROM ingredients` will show ~20 forms of "tablespoon"
- Fix approach: Add a small alias → canonical map (e.g. `tbsp|tablespoons|tablespoon → tbsp`) at parse time in `backend/scraper.py`, OR do it at read time in the scaler — decide before Phase 4

**Coarse DB error handling:**
- Issue: `except Exception as e` around the DB insert block maps every failure to HTTP 500 with the raw exception message in the body
- Files: `backend/main.py:77-78`
- Impact: Schema violations, FK failures, and disk-full all look identical to the client; exception message may leak internal paths
- Fix approach: Catch specific `sqlite3.IntegrityError` / `sqlite3.OperationalError`, drop the raw message from the 500 response body (log it instead once logging exists)

**No transaction boundary for multi-table inserts:**
- Issue: `recipes` is inserted, then `ingredients`, then `steps` in three separate `sqlite-utils` calls. If the ingredients insert fails, a headless `recipes` row is orphaned.
- Files: `backend/main.py:57-76`
- Impact: Partial writes on failure; manual cleanup required
- Fix approach: Wrap the three inserts in `with db.conn: ...` (sqlite-utils exposes `db.conn` for raw transactional blocks) or use `db.execute("BEGIN")` / `COMMIT` explicitly

**Broad `except Exception` in scraper tier helpers:**
- Issue: `_try_scrape_me` and `_try_recipe_scrapers_html` catch `_SCRAPER_RECOVERABLE` then fall through to `except Exception: return None`
- Files: `backend/scraper.py:127-129, 138-140`
- Impact: Real bugs (import errors, programmer mistakes) get silently swallowed as "tier didn't work, try the next one"
- Fix approach: Narrow the second except to `(ValueError, AttributeError, KeyError)` — everything genuinely recoverable — and let truly unexpected errors propagate

## Known Bugs

**None confirmed as active.** Historical issues resolved during Phase 2:
- AllRecipes 403 via `httpx` fetch — worked around by making `scrape_me` the Tier-1 path (it uses its own fetcher that passes AllRecipes' TLS fingerprint check). `httpx._fetch` (`backend/scraper.py:110-119`) still 403s on AllRecipes and similar Akamai-protected sites; that's acceptable because Tier-1 now handles them.
- Brotli decoding failures — fixed by adding `brotli>=1.2.0` to `pyproject.toml`
- Claude JSON truncation — fixed by raising `CLAUDE_MAX_TOKENS` to 4096 and adding explicit `stop_reason == "max_tokens"` detection at `backend/scraper.py:318-322`

## Security Considerations

**CORS allows only `localhost:5173` — dev-only:**
- Risk: Once deployed to Render, the React app will be on the same origin (FastAPI serves `frontend/dist`), so CORS is effectively unused in prod. But the hardcoded `http://localhost:5173` in `backend/main.py:21` is a reminder that CORS config is not environment-aware.
- Files: `backend/main.py:19-25`
- Current mitigation: None needed for same-origin production
- Recommendations: Either read from env (`ALLOWED_ORIGINS`) or drop CORS entirely in production; document the intent

**No authentication on any endpoint:**
- Risk: Anyone who can reach the Render URL can `POST /api/recipes/url`, `DELETE /api/recipes/{id}`, etc., and burn through the Anthropic API quota (Claude fallback tier)
- Files: `backend/main.py` (all routes)
- Current mitigation: None. Personal single-user app assumption.
- Recommendations: At minimum, add an `X-API-Key` header check using an env var before exposing to the public internet. Anthropic spend can compound if an attacker POSTs URLs that defeat tiers 1 and 2.

**SSRF surface on `POST /api/recipes/url`:**
- Risk: Accepts any URL that parses as `HttpUrl`. An attacker can submit `http://169.254.169.254/latest/meta-data/` (AWS metadata) or `http://localhost:<other-port>/` to probe internal services; `httpx` will follow up to the default redirect chain.
- Files: `backend/scraper.py:110-119` (no host allowlist or blocklist)
- Current mitigation: None. `HttpUrl` accepts internal hostnames and private IPs.
- Recommendations: Before exposing publicly, add a check that resolves the hostname and rejects RFC 1918 / loopback / link-local targets before calling `client.get`

**Env-var leakage via exception messages:**
- Risk: `HTTPException(status_code=500, detail=f"Database error: {e}")` (`backend/main.py:78`) can echo file paths including the value of `DATABASE_URL`
- Files: `backend/main.py:78`
- Current mitigation: None
- Recommendations: Log the exception, return a generic message to the client

## Performance Bottlenecks

**`_page_text_for_claude` truncates at 20000 chars:**
- Problem: Some SPA pages (`__NEXT_DATA__` blobs) exceed this and Claude sees a mid-string cut
- Files: `backend/scraper.py:45, 296`
- Cause: Safety valve to keep Claude token spend bounded
- Improvement path: If a page exceeds the cap, heuristically prioritise the JSON blob over visible text (reversed order) since that's where the recipe lives on Next.js sites

**Synchronous `sqlite-utils` calls from async handler:**
- Problem: `POST /api/recipes/url` is `async def` but the DB insert block (`backend/main.py:56-76`) is sync and blocks the event loop for the duration of three inserts
- Files: `backend/main.py:55-76`
- Cause: `sqlite-utils` doesn't have an async API
- Improvement path: Low priority — SQLite inserts are microseconds. Only worth fixing (via `asyncio.to_thread`) if benchmark shows loop stalls under load.

**`scrape_me` runs in a thread per request:**
- Problem: Tier-1 path spawns a thread to wrap the blocking library call
- Files: `backend/scraper.py:125` (`asyncio.to_thread(scrape_me, url)`)
- Cause: `scrape_me` is sync and does its own HTTP
- Improvement path: Acceptable for now. At scale, consider a thread pool with a worker limit.

## Fragile Areas

**Static mount order in `backend/main.py`:**
- Files: `backend/main.py:96-99`
- Why fragile: `app.mount("/", StaticFiles(...))` catches **everything not already registered**. Any route added after it will be shadowed by the SPA's `index.html`.
- Safe modification: Add new API routes **above** the mount block. The `try/except RuntimeError` around it exists specifically so the server still starts when `frontend/dist` doesn't exist — do not simplify it away.
- Test coverage: No test exercises the static mount behaviour or the mount-order invariant.

**DB singleton with module-global state:**
- Files: `backend/db.py:6, 64`
- Why fragile: `_db` is a module-level cache. Any test that changes `DATABASE_URL` must also do `backend.db._db = None` before and after, otherwise a stale connection to the wrong path leaks between tests.
- Safe modification: If touching `get_db`, preserve the `is not None` short-circuit and keep the reset escape hatch documented. See `tests/test_scraper.py:113, 148, 159` for the required idiom.
- Test coverage: Covered in `IngestUrlEndpointTests` by `TemporaryDirectory` + explicit reset.

**Ingredient-parsing regex:**
- Files: `backend/scraper.py:417-426` (`_INGREDIENT_RE`)
- Why fragile: The regex was iteratively fixed for specific sites (Budget Bytes `"1 large egg"` → unit "l", `"⅓ cup"` → 1.0, "lbs." residual dot, paren-wrapped commas). Any tweak risks regressing one of these.
- Safe modification: Add a regression test in `tests/test_scraper.py` for any new input you're trying to fix **before** changing the regex.
- Test coverage: `test_quantity_parser_handles_fraction_edge_cases` covers quantity only. Unit/name/preparation extraction has no dedicated unit tests beyond the one embedded in `test_recipe_scrapers_html_normalizes_schema_recipe`.

**Dotenv must load before any local import:**
- Files: `backend/main.py:1-3`
- Why fragile: If someone adds `from backend.scraper import ...` above `load_dotenv()`, scraper module will be imported before env is populated — but scraper only reads `ANTHROPIC_API_KEY` lazily inside `_claude_extract`, so today nothing breaks. That safety is implicit.
- Safe modification: Never move `load_dotenv()` below local imports. Keep the current two-phase layout (stdlib → dotenv → `import` blocks).

## Scaling Limits

**SQLite single-writer:**
- Current capacity: WAL mode enabled (`backend/db.py:19`) — many readers, one writer
- Limit: Concurrent `POST /api/recipes/url` requests serialise on the writer lock
- Scaling path: Acceptable for personal use; if multi-user emerges, move to Postgres

**Render free tier:**
- Current capacity: 1 GB persistent disk at `/data`
- Limit: At ~1 KB per recipe row + embedded ingredients/steps, disk space is effectively unbounded for personal use. Free-tier idle shutdown (15 min) means the first request after idle has cold-start latency.
- Scaling path: Upgrade to paid Render tier, or switch to a provider without idle shutdown

## Dependencies at Risk

**`recipe-scrapers >=15.11.0`:**
- Risk: The library drops/adds site adapters frequently; version-to-version behaviour on a given URL can change
- Impact: A recipe that parsed via Tier 1 today may fall through to Tier 2 or Tier 3 after a `uv sync` upgrade
- Migration plan: Pin to a tested version in `pyproject.toml` before deploying; run the scraper test suite + a handful of real-URL smoke tests before bumping

**`anthropic` SDK:**
- Risk: SDK breaking changes are rare but the `claude-sonnet-4-20250514` model ID is hardcoded at `backend/scraper.py:43`. Anthropic can deprecate model snapshots.
- Impact: Tier-3 fallback starts returning 404/400 from the API
- Migration plan: Watch Anthropic deprecation notices; when bumping, update `CLAUDE_MODEL` and re-run the truncation/JSON tests

## Missing Critical Features

**No way to list or view recipes from the client:**
- Problem: `GET /api/recipes` returns `[]` and `GET /api/recipes/{id}` always 404s (stubs)
- Blocks: Frontend can't render a list or detail page — blocks Phase 5

**Photo/PDF ingestion not implemented:**
- Problem: `POST /api/recipes/upload` is a stub
- Blocks: Phase 3 per the build order in `CLAUDE.md`; `backend/parser.py` doesn't exist yet

**Serving-size scaler not implemented:**
- Problem: `GET /api/recipes/{id}/scale` route is documented in `AGENTS.md`/`CLAUDE.md` but not defined in `backend/main.py`
- Blocks: Phase 4; `backend/scaler.py` doesn't exist yet

**No delete flow:**
- Problem: `DELETE /api/recipes/{recipe_id}` is a stub. Additionally, with FKs enabled, a naive delete will fail — children (`ingredients`, `steps`) must be deleted first.
- Blocks: Any UI "Remove recipe" button

## Test Coverage Gaps

**Untested: end-to-end scraper tier selection**
- What's not tested: Tier-1 (`scrape_me`) success path, Tier-1 → Tier-2 fallback, Tier-2 → Tier-3 fallback, `source` field correctness across all three
- Files: `backend/scraper.py:80-107`
- Risk: Regression in the cascade logic (e.g. silently skipping a tier) would not be caught
- Priority: Medium — fixtures for all three paths would catch most future bugs

**Untested: ingredient parser edge cases**
- What's not tested: `"1 large egg"`, `"⅓ cup milk"`, `"2 cups (500 ml) flour, sifted"`, `"lbs."` residual dot — all known hard cases from Phase 2 debugging
- Files: `backend/scraper.py:417-463`
- Risk: The regex is fragile (see above). A future "clean up" could regress any of these.
- Priority: High — cheap to add as straight `assertEqual` tests

**Untested: ClaudeExtractError → HTTP 422 translation**
- What's not tested: Missing API key, truncated response, malformed JSON from Claude — the observable failure modes should each produce a 422 with a useful `detail`
- Files: `backend/scraper.py:299-334`, `backend/main.py:52-53`
- Risk: Regressions in error message wording would confuse future debugging
- Priority: Low — covered implicitly by manual curl testing

**Untested: DB constraints**
- What's not tested: FK enforcement (deleting a recipe with children should fail or cascade), WAL mode persistence across restarts
- Files: `backend/db.py`
- Risk: The Phase-3 delete endpoint will hit FK errors if written naively
- Priority: Medium — add tests alongside the delete-recipe implementation

---

*Concerns audit: 2026-04-20*

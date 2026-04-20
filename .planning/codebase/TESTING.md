# Testing Patterns

**Analysis Date:** 2026-04-20

## Test Framework

**Runner:**
- Python stdlib `unittest` — no `pytest`, no `pytest.ini`, no `conftest.py`
- Tests defined as `unittest.TestCase` subclasses

**Assertion Library:**
- `unittest.TestCase` methods: `assertEqual`, `assertIsNotNone`
- Raw `assert` for mypy/Pyright narrowing after `assertIsNotNone` (see `tests/test_scraper.py:47`)

**HTTP Testing:**
- `fastapi.testclient.TestClient` for endpoint tests (`tests/test_scraper.py:7, 138`)

**Run Commands:**
```bash
uv run python -m unittest discover -s tests           # Run all tests
uv run python -m unittest tests.test_scraper          # Run one module
uv run python -m unittest tests.test_scraper.ScraperTests.test_quantity_parser_handles_fraction_edge_cases   # Run one test
uv run python tests/test_scraper.py                   # Works via unittest.main() at bottom of file
```

No watch mode, no coverage tooling (`coverage`, `pytest-cov` — none installed).

## Test File Organization

**Location:**
- Separate `tests/` directory at project root, mirroring `backend/` module names
- Not co-located with source (no `backend/test_*.py`)

**Naming:**
- Files: `test_<module>.py` (e.g. `tests/test_scraper.py` tests `backend/scraper.py`)
- Classes: `<Feature>Tests` (`ScraperTests`, `IngestUrlEndpointTests`)
- Methods: `test_<what>_<expected>` — descriptive snake_case, often long (`test_recipe_scrapers_html_normalizes_schema_recipe`, `test_ingest_url_inserts_recipe_ingredients_and_steps`)

**Structure:**
```
tests/
├── __pycache__/                 # gitignored
└── test_scraper.py              # single test module right now
```

## Test Structure

**Suite Organization:**
```python
# tests/test_scraper.py:42
class ScraperTests(unittest.TestCase):
    def test_recipe_scrapers_html_normalizes_schema_recipe(self):
        recipe = _try_recipe_scrapers_html(RECIPE_SCHEMA_HTML, "https://example.com/test")
        self.assertIsNotNone(recipe)
        assert recipe is not None                           # type-narrowing assert
        self.assertEqual(recipe["title"], "Test Pancakes")
        ...
```

**Patterns:**
- **Module-level HTML fixture:** `RECIPE_SCHEMA_HTML` (`tests/test_scraper.py:12-39`) is a realistic schema.org JSON-LD recipe page, used as test input so the regex/parser runs end-to-end
- **Import private helpers directly:** tests import `_normalise_claude`, `_parse_quantity`, `_try_recipe_scrapers_html` (`tests/test_scraper.py:9`). Leading-underscore doesn't block test access.
- **One assertion block per behaviour:** each test verifies a full shape by asserting every field, rather than many micro-tests
- **Type narrowing:** after `assertIsNotNone`, add a bare `assert x is not None` so Pyright/mypy understand later subscripting

## Mocking

**Framework:** Hand-rolled monkeypatching — no `unittest.mock`, no `pytest-mock`.

**Patterns:**
```python
# tests/test_scraper.py:116-137 — replace scrape_url with a stub on the imported module
async def fake_scrape_url(url: str) -> dict:
    return {
        "title": "Smoke Test Recipe",
        "source_url": url,
        "servings": 4,
        "prep_min": 10,
        "cook_min": 20,
        "cuisine": "Test",
        "tags": ["dinner"],
        "ingredients": [{"quantity": 1.5, "unit": "cups", "name": "flour", "preparation": ""}],
        "steps": [{"step_number": 1, "instruction": "Mix."}],
        "source": "recipe-scrapers",
    }

main_module.scrape_url = fake_scrape_url   # overwrite the module-level name
```

**What to Mock:**
- External network calls — never hit `recipe-scrapers.scrape_me` or Claude's API in tests; stub `scrape_url` or the individual tier helpers
- Wall-clock time if it appears in assertions (not currently present)

**What NOT to Mock:**
- SQLite — tests use a real temp-file SQLite via `TemporaryDirectory` + `DATABASE_URL` override (`tests/test_scraper.py:106-109`). This is intentional: the DB layer is fast and cheap, and mocking it would defeat the point.
- `sqlite-utils` internals
- The parsers/normalisers themselves — they're pure and should be tested directly (see the three unit tests in `ScraperTests`)

## Fixtures and Factories

**Test Data:**
```python
# Module-level HTML fixture as a bare string constant (tests/test_scraper.py:12)
RECIPE_SCHEMA_HTML = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
      { ... }
    </script>
  </head>
</html>
"""

# Inline dict for normaliser input (tests/test_scraper.py:68-83)
recipe = _normalise_claude({"title": "  Test   Recipe ", ...}, "https://example.com/claude")
```

**Location:**
- Inline in the test module — no `fixtures/` directory
- For larger HTML samples in future, prefer a `tests/fixtures/<site>.html` file loaded via `Path(__file__).parent / "fixtures" / "x.html"`

## Coverage

**Requirements:** None enforced.

**View Coverage:** Not configured. If needed: `uv add --dev coverage && uv run coverage run -m unittest discover tests && uv run coverage report`.

## Test Types

**Unit Tests:**
- Scope: one function / one behaviour — `_parse_quantity`, `_normalise_claude`, `_try_recipe_scrapers_html`
- Approach: call the function with a hand-crafted input, assert full output shape

**Integration Tests:**
- Scope: HTTP boundary → scraper → DB — `IngestUrlEndpointTests.test_ingest_url_inserts_recipe_ingredients_and_steps`
- Approach:
  1. Create a `TemporaryDirectory` and set `DATABASE_URL` to a path inside it
  2. **Critically reset `backend.db._db = None`** so the next `get_db()` rebuilds against the new path
  3. `importlib.reload(main_module)` so `@app.post(...)` registrations pick up the new DB state
  4. Monkeypatch `main_module.scrape_url` to a stub
  5. POST via `TestClient`, assert status + body
  6. Reset the DB singleton again and query tables directly to verify rows
  7. `finally:` restore `DATABASE_URL` and clear `_db`

**E2E Tests:** Not used.

## Common Patterns

**Async Testing:**
- Current tests don't directly `await` async functions; they exercise async code indirectly via `TestClient` (which runs the app synchronously)
- If testing an `async def` helper in isolation, use `asyncio.run(...)` rather than adding `pytest-asyncio`

**Error Testing:**
- No explicit `assertRaises` usage yet; add `with self.assertRaises(ValueError): ...` when testing the `ClaudeExtractError` → `ValueError` translation paths

**DB Singleton Reset (IMPORTANT):**
```python
# tests/test_scraper.py:113, 148, 159 — this pattern MUST bracket any test that
# changes DATABASE_URL or needs a fresh DB:
import backend.db as db_module
db_module._db = None        # before: forget the cached connection
# ... test body ...
db_module._db = None        # after: don't leak the temp DB into other tests
```

Forgetting to reset `_db` causes later tests to hit a stale path and silently pass/fail.

---

*Testing analysis: 2026-04-20*

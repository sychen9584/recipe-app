# Recipe App — Claude Code Context

## Project overview
A personal food recipe web app. Ingest recipes from URLs, photos, and PDFs.
Store them in a uniform schema. Browse, search, and scale serving sizes with
unit conversion. Hosted on Render (free tier) as a single service.

## Tech stack
- **Backend**: Python · FastAPI · uvicorn · sqlite-utils
- **Frontend**: React · Vite (built to `frontend/dist/`, served by FastAPI)
- **Database**: SQLite stored at path from `DATABASE_URL` env var
- **AI**: Anthropic API (`claude-sonnet-4-20250514`) for URL fallback parsing
  and photo/PDF extraction via Vision
- **Hosting**: Render — one web service, persistent disk mounted at `/data`
- **Package manager**: uv (replaces pip + venv)

## Repo structure
```
recipe-app/
  backend/
    main.py          # FastAPI app entry point; also mounts frontend/dist/
    db.py            # sqlite-utils Database instance + insert_recipe helper
    scraper.py       # URL ingestion: recipe_scrapers first, Claude fallback
    parser.py        # Photo + PDF ingestion via Claude Vision
    scaler.py        # Serving size scaling + unit conversion (Pint)
    pyproject.toml   # project metadata + dependencies (uv manages this)
  frontend/
    src/
      App.jsx
      RecipeList.jsx
      RecipeDetail.jsx
      AddRecipe.jsx
    vite.config.js   # proxies /api → localhost:8000 in dev
    package.json
  render.yaml
  .env.example
  .gitignore
  CLAUDE.md          # this file
```

## Python environment (uv)
Always use uv — never call pip or python directly.

```bash
# Install uv (once, globally in WSL2)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create venv + install all deps from pyproject.toml
uv sync

# Add a new dependency (updates pyproject.toml + uv.lock automatically)
uv add anthropic

# Run the dev server (uv runs inside the venv automatically — no activation needed)
uv run uvicorn backend.main:app --reload --port 8000

# Run any python script
uv run python backend/db.py
```

The venv lives at `.venv/` — already gitignored. uv creates and manages it
automatically on first `uv sync`. No manual activation needed when using
`uv run`.

## pyproject.toml
```toml
[project]
name = "recipe-app"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi",
    "uvicorn[standard]",
    "sqlite-utils",
    "python-multipart",
    "httpx",
    "beautifulsoup4",
    "anthropic",
    "pint",
    "python-dotenv",
    "h2",
    "brotli",
    "recipe-scrapers",
]
```

## Database schema (SQLite via sqlite-utils)
```
recipes      id, title, source_url, servings, prep_min, cook_min,
             cuisine, tags (JSON), created_at
ingredients  id, recipe_id (FK), quantity (REAL), unit, name, preparation
steps        id, recipe_id (FK), step_number, instruction
```

## API routes
```
GET    /api/recipes            list all; ?q= search, ?tag= filter
GET    /api/recipes/{id}       full detail
POST   /api/recipes/url        body: {"url": "..."} → scrape + store
POST   /api/recipes/upload     multipart: file (image or PDF) → Claude Vision
DELETE /api/recipes/{id}       remove recipe
GET    /api/recipes/{id}/scale?servings=N&unit=metric|imperial
```

Upload accepts JPEG, PNG, WEBP, GIF, and PDF files. The backend rejects unsupported
types with 415 and files over 20 MB with 413 before calling Claude. Uploads store
`source_url` as `upload:{filename}` and return a response-only `source` of
`upload-image` or `upload-pdf`.

Scale accepts `servings` from 1 to 100 and `unit` as `metric` or `imperial`.
The backend stores raw float quantities and computes `display_quantity` plus
`display_unit` at request time so unit-system preferences and frontend formatting
can evolve without rewriting stored recipe rows.

## Environment variables
```
DATABASE_URL        ./recipes.db (local) | /data/recipes.db (Render)
ANTHROPIC_API_KEY   sk-ant-...
```
Load via `python-dotenv` in dev. On Render, set in the dashboard directly.

## Local dev workflow
```bash
# Terminal 1 — backend
uv run uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend
cd frontend
npm run dev        # Vite at localhost:5173, proxies /api → :8000
```

## Render deploy (render.yaml)
```yaml
services:
  - type: web
    name: recipe-app
    buildCommand: pip install uv && uv sync && cd frontend && npm i && npm run build
    startCommand: uv run uvicorn backend.main:app --host 0.0.0.0 --port $PORT
    disk:
      name: recipe-data
      mountPath: /data
      sizeGB: 1
```

## Key conventions
- All API routes are prefixed `/api/`. FastAPI static mount (`/*`) comes LAST
  in main.py so it never shadows API routes.
- Database path always comes from `os.getenv("DATABASE_URL", "./recipes.db")`.
  Never hardcode a path.
- Persist recipes with `insert_recipe(db, recipe)` so URL and upload ingestion use
  the same explicit column list and child-table inserts.
- Ingredients store `quantity` as a float and `unit` as a plain string.
  The scaler converts units using Pint; display uses fraction rounding
  (e.g. 0.5 → ½, 0.333 → ⅓).
- Serving scaling is direct multiplication by target/original servings; Pint is
  used only for unit conversion after the scaled raw quantity is known.
- Claude API model: always use `claude-sonnet-4-20250514`. Max tokens 4096
  for parsing tasks.
- Claude URL fallback and photo/PDF upload parsing share
  `normalise_claude(raw, source_url)` to avoid drift in recipe JSON cleanup.
- Frontend calls backend as `${import.meta.env.VITE_API_URL}/api/...`.
  `VITE_API_URL` defaults to empty string (same origin) in production.

## Build order (follow this sequence)
1. Backend skeleton — done: FastAPI, SQLite schema, GET /api/recipes returns []
2. URL ingestion — done: recipe_scrapers scrape_me → scrape_html → Claude fallback
3. Photo + PDF ingestion — done: parser.py + POST /api/recipes/upload
4. Serving scaler — done: scaler.py + GET /api/recipes/{id}/scale
5. React frontend — scaffold components, wire to API
6. Deploy config — render.yaml, verify persistent disk

## What I'm learning
I have a Python background (NumPy, pandas, FastAPI is new to me).
React and JavaScript are beginner level — Claude Code scaffolds the frontend.
After generating each file, explain the key design decisions and why.
Flag anything I should understand before moving to the next step.

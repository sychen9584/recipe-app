# AGENTS.md — Recipe App

## Project Overview
A personal recipe web application that:
- Ingests recipes from URLs, photos, and PDFs
- Normalizes them into a consistent schema
- Supports browsing, search, and serving-size scaling with unit conversion
- Runs as a single-service deployment on Render with persistent SQLite storage

## Tech Stack
Backend: Python (>=3.11), FastAPI, uvicorn, sqlite-utils  
Frontend: React, Vite  
Database: SQLite via DATABASE_URL  
AI: Anthropic API (claude-sonnet-4-20250514)  
Hosting: Render (persistent disk at /data)  
Package manager: uv (required)

## Repository Structure
recipe-app/
  backend/
    main.py
    db.py
    scraper.py
    parser.py
    scaler.py
    pyproject.toml
  frontend/
    src/
      App.jsx
      RecipeList.jsx
      RecipeDetail.jsx
      AddRecipe.jsx
    vite.config.js
    package.json
  render.yaml
  .env.example
  .gitignore
  AGENTS.md

## Required Workflow Rules
- Always use uv (never pip)
- Always run Python via `uv run`
- Do not hardcode database paths
- Preserve /api route structure
- Keep single-service architecture
- Do not override API routes with frontend static mount

## Python Environment
uv sync
uv run uvicorn backend.main:app --reload --port 8000
uv run python backend/db.py
uv add <package>

## Dependencies
fastapi
uvicorn[standard]
sqlite-utils
python-multipart
httpx
beautifulsoup4
anthropic
pint
python-dotenv

## Database Schema
recipes: id, title, source_url, servings, prep_min, cook_min, cuisine, tags, created_at  
ingredients: id, recipe_id, quantity, unit, name, preparation  
steps: id, recipe_id, step_number, instruction  

## API Contract
GET    /api/recipes  
GET    /api/recipes/{id}  
POST   /api/recipes/url  
POST   /api/recipes/upload  
DELETE /api/recipes/{id}  
GET    /api/recipes/{id}/scale  

## Environment Variables
DATABASE_URL  
ANTHROPIC_API_KEY  

Defaults:
./recipes.db (local)  
/data/recipes.db (Render)

## Frontend Integration
- Backend serves frontend/dist
- API calls use ${import.meta.env.VITE_API_URL}/api/...
- VITE_API_URL defaults to empty string in production

## Implementation Conventions
- quantity = float
- unit = string
- use Pint for conversion
- use claude-sonnet-4-20250514
- max tokens 4096
- prefer schema.org parsing before AI fallback

## Build Order
1. Backend skeleton
2. URL ingestion
3. Photo/PDF ingestion
4. Scaler
5. Frontend
6. Deployment

## Deployment
Single Render service with persistent disk at /data

## Do Not Change Without Approval
- Deployment model
- SQLite usage
- API routes
- React + Vite
- uv package manager

## Output Expectations
- Make minimal complete changes
- Preserve architecture
- State assumptions
- Summarize changes and why
- Call out risks and next steps

## Preferred Behavior
- Do not ask unnecessary questions
- Make reasonable assumptions
- Prefer working implementations
- Avoid adding new frameworks

## Validation Checklist
- Code runs
- Imports valid
- API intact
- No hardcoded paths
- frontend/dist unchanged

from dotenv import load_dotenv

load_dotenv()

import json
from typing import Literal

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.db import get_db, insert_recipe
from backend.parser import MAX_UPLOAD_BYTES, SUPPORTED_DOC_TYPES, SUPPORTED_IMAGE_TYPES, parse_upload
from backend.scaler import scale_ingredients
from backend.scraper import scrape_url

app = FastAPI(title="Recipe App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlIn(BaseModel):
    url: HttpUrl


@app.get("/api/recipes")
def list_recipes(q: str | None = None, tag: str | None = None):
    db = get_db()
    sql = (
        "select id, title, source_url, servings, prep_min, cook_min, cuisine, tags, created_at "
        "from recipes"
    )
    params: list[str] = []
    if q:
        sql += " where lower(title) like ?"
        params.append(f"%{q.lower()}%")
    sql += " order by created_at desc, id desc"

    recipes = [_normalise_recipe_row(row) for row in db.query(sql, params)]
    if tag:
        tag_key = tag.lower()
        recipes = [
            recipe
            for recipe in recipes
            if any(existing.lower() == tag_key for existing in recipe["tags"])
        ]
    return recipes


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    recipe = _get_recipe_detail(get_db(), recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.get("/api/recipes/{recipe_id}/scale")
def scale_recipe(
    recipe_id: int,
    servings: int | None = Query(default=None, ge=1, le=100),
    unit: Literal["imperial", "metric"] = "imperial",
):
    db = get_db()
    recipe = _get_recipe_detail(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    target_servings = servings or recipe.get("servings") or 1

    return {
        **recipe,
        "servings": target_servings,
        "original_servings": recipe.get("servings") or 0,
        "unit_system": unit,
        "ingredients": scale_ingredients(
            recipe["ingredients"],
            original_servings=recipe.get("servings") or 0,
            target_servings=target_servings,
            unit_system=unit,
        ),
    }


@app.post("/api/recipes/url", status_code=201)
async def ingest_url(payload: UrlIn):
    url = str(payload.url)

    try:
        recipe = await scrape_url(url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=422, detail=f"Source returned {e.response.status_code}")
    except httpx.HTTPError as e:
        raise HTTPException(status_code=422, detail=f"Could not fetch URL: {e}")
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        recipe_id = insert_recipe(get_db(), recipe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return JSONResponse(
        status_code=201,
        content={"id": recipe_id, **recipe},
    )


SUPPORTED_UPLOAD_TYPES = SUPPORTED_IMAGE_TYPES | SUPPORTED_DOC_TYPES


@app.post("/api/recipes/upload", status_code=201)
async def ingest_upload(file: UploadFile = File(...)):
    media_type = file.content_type or ""
    if media_type not in SUPPORTED_UPLOAD_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {media_type}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload too large: {len(file_bytes)} bytes (max {MAX_UPLOAD_BYTES})",
        )

    try:
        recipe = await parse_upload(file_bytes, media_type, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    try:
        recipe_id = insert_recipe(get_db(), recipe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return JSONResponse(
        status_code=201,
        content={"id": recipe_id, **recipe},
    )


@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    db = get_db()
    if _get_recipe_row(db, recipe_id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    db.execute("delete from ingredients where recipe_id = ?", [recipe_id])
    db.execute("delete from steps where recipe_id = ?", [recipe_id])
    db.execute("delete from recipes where id = ?", [recipe_id])
    return {"status": "deleted", "id": recipe_id}


try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except RuntimeError:
    pass


def _get_recipe_row(db, recipe_id: int) -> dict | None:
    rows = list(
        db.query(
            "select id, title, source_url, servings, prep_min, cook_min, cuisine, tags, created_at "
            "from recipes where id = ?",
            [recipe_id],
        )
    )
    return rows[0] if rows else None


def _get_recipe_detail(db, recipe_id: int) -> dict | None:
    recipe = _get_recipe_row(db, recipe_id)
    if recipe is None:
        return None

    return {
        **_normalise_recipe_row(recipe),
        "ingredients": list(
            db.query(
                "select id, recipe_id, quantity, unit, name, preparation "
                "from ingredients where recipe_id = ? order by id",
                [recipe_id],
            )
        ),
        "steps": list(
            db.query(
                "select id, recipe_id, step_number, instruction "
                "from steps where recipe_id = ? order by step_number, id",
                [recipe_id],
            )
        ),
    }


def _normalise_recipe_row(row: dict) -> dict:
    return {**row, "tags": _decode_tags(row.get("tags"))}


def _decode_tags(value) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []

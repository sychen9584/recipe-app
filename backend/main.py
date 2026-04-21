from dotenv import load_dotenv

load_dotenv()

import json
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.db import get_db, insert_recipe
from backend.parser import MAX_UPLOAD_BYTES, SUPPORTED_DOC_TYPES, SUPPORTED_IMAGE_TYPES, parse_upload
from backend.scaler import DEFAULT_SERVINGS, scale_ingredients
from backend.scraper import scrape_url

app = FastAPI(title="Recipe App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UrlIn(BaseModel):
    url: HttpUrl


class RecipeUpdate(BaseModel):
    title: Optional[str] = None
    cuisine: Optional[str] = None
    prep_min: Optional[int] = None
    cook_min: Optional[int] = None
    tags: Optional[list[str]] = None


@app.get("/api/recipes")
def list_recipes(q: str = "", tag: str = ""):
    db = get_db()
    sql = (
        "select id, title, source_url, servings, prep_min, cook_min, cuisine, tags, created_at "
        "from recipes where 1 = 1"
    )
    params: list[str] = []
    search = q.strip()
    active_tag = tag.strip()

    if search:
        sql += " and (lower(title) like lower(?) or lower(tags) like lower(?))"
        params.extend([f"%{search}%", f"%{search}%"])

    if active_tag:
        sql += " and lower(tags) like lower(?)"
        params.append(f"%{json.dumps(active_tag)}%")

    sql += " order by created_at desc, id desc"
    return [_normalise_recipe_row(row) for row in db.query(sql, params)]


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    recipe = _get_recipe_detail(get_db(), recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


@app.patch("/api/recipes/{recipe_id}")
def update_recipe(recipe_id: int, payload: RecipeUpdate):
    db = get_db()
    if _get_recipe_row(db, recipe_id) is None:
        raise HTTPException(status_code=404, detail="Recipe not found")

    updates = _validated_recipe_updates(payload)
    if updates:
        assignments = ", ".join(f"{column} = ?" for column in updates)
        values = list(updates.values())
        db.execute(f"update recipes set {assignments} where id = ?", [*values, recipe_id])

    updated = _get_recipe_detail(db, recipe_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return updated


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

    original_servings = recipe.get("servings") or DEFAULT_SERVINGS
    target_servings = servings or original_servings

    return {
        **recipe,
        "servings": target_servings,
        "original_servings": original_servings,
        "unit_system": unit,
        "ingredients": scale_ingredients(
            recipe["ingredients"],
            original_servings=original_servings,
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


def _validated_recipe_updates(payload: RecipeUpdate) -> dict:
    updates = payload.model_dump(exclude_none=True)

    if "title" in updates:
        title = updates["title"].strip()
        if not title:
            raise HTTPException(status_code=422, detail="title must be a non-empty string")
        updates["title"] = title

    if "cuisine" in updates:
        updates["cuisine"] = updates["cuisine"].strip()

    for field in ("prep_min", "cook_min"):
        if field in updates and updates[field] < 0:
            raise HTTPException(status_code=422, detail=f"{field} must be >= 0")

    if "tags" in updates:
        cleaned_tags = []
        for tag in updates["tags"]:
            cleaned = tag.strip()
            if not cleaned:
                raise HTTPException(
                    status_code=422,
                    detail="tags must be an array of non-empty strings",
                )
            cleaned_tags.append(cleaned)
        updates["tags"] = json.dumps(cleaned_tags)

    return updates


def _decode_tags(value) -> list[str]:
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return []
    return decoded if isinstance(decoded, list) else []

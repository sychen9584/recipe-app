from dotenv import load_dotenv

load_dotenv()

import json

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.db import get_db
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
def list_recipes():
    return []


@app.get("/api/recipes/{recipe_id}")
def get_recipe(recipe_id: int):
    raise HTTPException(status_code=404, detail="Recipe not found")


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
        db = get_db()
        recipe_id = db["recipes"].insert(
            {
                "title": recipe["title"],
                "source_url": recipe["source_url"],
                "servings": recipe["servings"],
                "prep_min": recipe["prep_min"],
                "cook_min": recipe["cook_min"],
                "cuisine": recipe["cuisine"],
                "tags": json.dumps(recipe["tags"]),
            }
        ).last_pk

        if recipe["ingredients"]:
            db["ingredients"].insert_all(
                [{**ing, "recipe_id": recipe_id} for ing in recipe["ingredients"]]
            )
        if recipe["steps"]:
            db["steps"].insert_all(
                [{**step, "recipe_id": recipe_id} for step in recipe["steps"]]
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return JSONResponse(
        status_code=201,
        content={"id": recipe_id, **recipe},
    )


@app.post("/api/recipes/upload")
def ingest_upload(file: UploadFile = File(...)):
    return {"status": "not implemented"}


@app.delete("/api/recipes/{recipe_id}")
def delete_recipe(recipe_id: int):
    return {"status": "not implemented"}


try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except RuntimeError:
    pass

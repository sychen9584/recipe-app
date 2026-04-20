from dotenv import load_dotenv

load_dotenv()

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl

from backend.db import get_db, insert_recipe
from backend.parser import MAX_UPLOAD_BYTES, SUPPORTED_DOC_TYPES, SUPPORTED_IMAGE_TYPES, parse_upload
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
    return {"status": "not implemented"}


try:
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
except RuntimeError:
    pass

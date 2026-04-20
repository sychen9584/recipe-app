import json
import os
import sqlite3
from datetime import datetime, timezone

import sqlite_utils

_db: sqlite_utils.Database | None = None


def get_db() -> sqlite_utils.Database:
    """Return a singleton sqlite-utils Database, creating tables on first call."""
    global _db
    if _db is not None:
        return _db

    path = os.getenv("DATABASE_URL", "./recipes.db")
    conn = sqlite3.connect(path, check_same_thread=False)
    db = sqlite_utils.Database(conn)

    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA journal_mode = WAL")

    if "recipes" not in db.table_names():
        db["recipes"].create(
            {
                "id": int,
                "title": str,
                "source_url": str,
                "servings": int,
                "prep_min": int,
                "cook_min": int,
                "cuisine": str,
                "tags": str,
                "created_at": str,
            },
            pk="id",
            defaults={"created_at": datetime.now(timezone.utc).isoformat()},
        )

    if "ingredients" not in db.table_names():
        db["ingredients"].create(
            {
                "id": int,
                "recipe_id": int,
                "quantity": float,
                "unit": str,
                "name": str,
                "preparation": str,
            },
            pk="id",
            foreign_keys=[("recipe_id", "recipes", "id")],
        )

    if "steps" not in db.table_names():
        db["steps"].create(
            {
                "id": int,
                "recipe_id": int,
                "step_number": int,
                "instruction": str,
            },
            pk="id",
            foreign_keys=[("recipe_id", "recipes", "id")],
        )

    _db = db
    return _db


def insert_recipe(db: sqlite_utils.Database, recipe: dict) -> int:
    """Insert a normalised recipe dict into recipes/ingredients/steps. Returns the new recipe id.

    Explicit column list keeps stray keys (like "source") out of the recipes table.
    """
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

    return recipe_id

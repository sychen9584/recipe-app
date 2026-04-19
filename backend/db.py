import os
from datetime import datetime, timezone

import sqlite_utils

_db: sqlite_utils.Database | None = None


def get_db() -> sqlite_utils.Database:
    """Return a singleton sqlite-utils Database, creating tables on first call."""
    global _db
    if _db is not None:
        return _db

    path = os.getenv("DATABASE_URL", "./recipes.db")
    db = sqlite_utils.Database(path)

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

import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient


def test_recipe_read_routes_and_delete():
    with TemporaryDirectory() as tmp:
        previous_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = str(Path(tmp) / "recipes.db")
        try:
            import backend.db as db_module
            import backend.main as main_module

            db_module._db = None
            main_module = importlib.reload(main_module)
            db = db_module.get_db()
            first_id = db_module.insert_recipe(
                db,
                {
                    "title": "Lemon Pasta",
                    "source_url": "https://example.com/lemon",
                    "servings": 2,
                    "prep_min": 5,
                    "cook_min": 12,
                    "cuisine": "Italian",
                    "tags": ["dinner", "pasta"],
                    "ingredients": [
                        {
                            "quantity": 1.0,
                            "unit": "cup",
                            "name": "pasta water",
                            "preparation": "",
                        }
                    ],
                    "steps": [{"step_number": 1, "instruction": "Boil pasta."}],
                },
            )
            db_module.insert_recipe(
                db,
                {
                    "title": "Berry Smoothie",
                    "source_url": "https://example.com/smoothie",
                    "servings": 1,
                    "prep_min": 3,
                    "cook_min": 0,
                    "cuisine": "",
                    "tags": ["breakfast"],
                    "ingredients": [
                        {
                            "quantity": 2.0,
                            "unit": "cup",
                            "name": "berries",
                            "preparation": "frozen",
                        }
                    ],
                    "steps": [{"step_number": 1, "instruction": "Blend."}],
                },
            )
            db_module._db = None

            client = TestClient(main_module.app)

            list_response = client.get("/api/recipes")
            assert list_response.status_code == 200, list_response.text
            assert len(list_response.json()) == 2

            search_response = client.get("/api/recipes?q=lemon")
            assert search_response.status_code == 200, search_response.text
            assert [recipe["title"] for recipe in search_response.json()] == ["Lemon Pasta"]

            tag_response = client.get("/api/recipes?tag=breakfast")
            assert tag_response.status_code == 200, tag_response.text
            assert [recipe["title"] for recipe in tag_response.json()] == ["Berry Smoothie"]

            detail_response = client.get(f"/api/recipes/{first_id}")
            assert detail_response.status_code == 200, detail_response.text
            detail = detail_response.json()
            assert detail["title"] == "Lemon Pasta"
            assert detail["tags"] == ["dinner", "pasta"]
            assert detail["ingredients"][0]["name"] == "pasta water"
            assert detail["steps"][0]["instruction"] == "Boil pasta."

            scale_response = client.get(f"/api/recipes/{first_id}/scale?servings=4")
            assert scale_response.status_code == 200, scale_response.text
            scaled = scale_response.json()
            assert scaled["ingredients"][0]["quantity"] == 2.0
            assert scaled["ingredients"][0]["display_quantity"] == "2"

            delete_response = client.delete(f"/api/recipes/{first_id}")
            assert delete_response.status_code == 200, delete_response.text
            assert delete_response.json() == {"status": "deleted", "id": first_id}

            missing_response = client.get(f"/api/recipes/{first_id}")
            assert missing_response.status_code == 404
        finally:
            import backend.db as db_module

            db_module._db = None
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url


def test_delete_missing_recipe_returns_404():
    with TemporaryDirectory() as tmp:
        previous_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = str(Path(tmp) / "recipes.db")
        try:
            import backend.db as db_module
            import backend.main as main_module

            db_module._db = None
            main_module = importlib.reload(main_module)
            response = TestClient(main_module.app).delete("/api/recipes/999")
            assert response.status_code == 404
        finally:
            import backend.db as db_module

            db_module._db = None
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url

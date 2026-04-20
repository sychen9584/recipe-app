import importlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.db import insert_recipe
from backend.scaler import scale_ingredients, to_fraction_str


def test_scale_ingredients_doubles_quantity():
    result = scale_ingredients(
        [{"quantity": 1.0, "unit": "cup", "name": "flour", "preparation": ""}],
        original_servings=4,
        target_servings=8,
    )

    assert result[0]["quantity"] == 2.0
    assert result[0]["display_quantity"] == "2"
    assert result[0]["display_unit"] == "cups"


def test_fraction_display():
    assert to_fraction_str(0.5) == "½"
    assert to_fraction_str(1.5) == "1½"
    assert to_fraction_str(3.0) == "3"
    assert to_fraction_str(2.75) == "2¾"
    assert to_fraction_str(2.6) == "2.6"


def test_metric_conversion_cups_to_ml():
    result = scale_ingredients(
        [{"quantity": 1.0, "unit": "cup", "name": "milk", "preparation": ""}],
        original_servings=4,
        target_servings=4,
        unit_system="metric",
    )

    assert result[0]["quantity"] == 1.0
    assert result[0]["unit"] == "cup"
    assert result[0]["display_unit"] == "ml"
    assert float(result[0]["display_quantity"]) > 200


def test_unmapped_unit_passthrough():
    result = scale_ingredients(
        [{"quantity": 2.0, "unit": "clove", "name": "garlic", "preparation": ""}],
        original_servings=4,
        target_servings=8,
    )

    assert result[0]["quantity"] == 4.0
    assert result[0]["unit"] == "clove"
    assert result[0]["display_quantity"] == "4"
    assert result[0]["display_unit"] == "clove"


def test_scale_endpoint_returns_scaled_recipe():
    with TemporaryDirectory() as tmp:
        previous_database_url = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = str(Path(tmp) / "recipes.db")
        try:
            import backend.db as db_module
            import backend.main as main_module

            db_module._db = None
            main_module = importlib.reload(main_module)
            db = db_module.get_db()
            recipe_id = insert_recipe(
                db,
                {
                    "title": "Scale Test Recipe",
                    "source_url": "upload:test.pdf",
                    "servings": 4,
                    "prep_min": 5,
                    "cook_min": 10,
                    "cuisine": "Test",
                    "tags": ["scale"],
                    "ingredients": [
                        {
                            "quantity": 1.0,
                            "unit": "cup",
                            "name": "milk",
                            "preparation": "",
                        }
                    ],
                    "steps": [{"step_number": 1, "instruction": "Mix."}],
                },
            )
            db_module._db = None

            response = TestClient(main_module.app).get(
                f"/api/recipes/{recipe_id}/scale?servings=8&unit=metric"
            )

            assert response.status_code == 200, response.text
            body = response.json()
            assert body["id"] == recipe_id
            assert body["servings"] == 8
            assert body["original_servings"] == 4
            assert body["unit_system"] == "metric"
            assert body["ingredients"][0]["quantity"] == 2.0
            assert body["ingredients"][0]["unit"] == "cup"
            assert body["ingredients"][0]["display_unit"] == "ml"
            assert float(body["ingredients"][0]["display_quantity"]) > 400
            assert body["steps"][0]["instruction"] == "Mix."
        finally:
            import backend.db as db_module

            db_module._db = None
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url

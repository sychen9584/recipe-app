import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from backend.scraper import _normalise_claude, _parse_quantity, _try_recipe_scrapers_html


RECIPE_SCHEMA_HTML = """<!doctype html>
<html>
  <head>
    <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Test Pancakes",
        "recipeYield": "4 servings",
        "prepTime": "PT10M",
        "cookTime": "PT15M",
        "recipeCuisine": "American",
        "keywords": "breakfast, pancakes",
        "recipeIngredient": [
          "1 1/2 cups flour",
          "2 tbsp sugar",
          "1 cup milk"
        ],
        "recipeInstructions": [
          {"@type": "HowToStep", "text": "Mix ingredients."},
          {"@type": "HowToStep", "text": "Cook on griddle."}
        ]
      }
    </script>
  </head>
  <body></body>
</html>
"""


class ScraperTests(unittest.TestCase):
    def test_recipe_scrapers_html_normalizes_schema_recipe(self):
        recipe = _try_recipe_scrapers_html(RECIPE_SCHEMA_HTML, "https://example.com/test")

        self.assertIsNotNone(recipe)
        assert recipe is not None
        self.assertEqual(recipe["title"], "Test Pancakes")
        self.assertEqual(recipe["source_url"], "https://example.com/test")
        self.assertEqual(recipe["servings"], 4)
        self.assertEqual(recipe["prep_min"], 10)
        self.assertEqual(recipe["cook_min"], 15)
        self.assertEqual(recipe["cuisine"], "American")
        self.assertEqual(recipe["tags"], ["breakfast", "pancakes"])
        self.assertEqual(
            recipe["ingredients"][0],
            {"quantity": 1.5, "unit": "cups", "name": "flour", "preparation": ""},
        )
        self.assertEqual(
            recipe["steps"],
            [
                {"step_number": 1, "instruction": "Mix ingredients."},
                {"step_number": 2, "instruction": "Cook on griddle."},
            ],
        )

    def test_claude_normalization_cleans_and_filters_payload(self):
        recipe = _normalise_claude(
            {
                "title": "  Test   Recipe ",
                "servings": "4 servings",
                "prep_min": "5 minutes",
                "cook_min": "10",
                "cuisine": "  American ",
                "tags": "quick, dinner",
                "ingredients": [
                    {"quantity": "1/2", "unit": " cup ", "name": " flour "},
                    {"quantity": "", "unit": "", "name": ""},
                ],
                "steps": [{"instruction": " Mix. "}, {"instruction": ""}],
            },
            "https://example.com/claude",
        )

        self.assertEqual(recipe["title"], "Test Recipe")
        self.assertEqual(recipe["servings"], 4)
        self.assertEqual(recipe["prep_min"], 5)
        self.assertEqual(recipe["cook_min"], 10)
        self.assertEqual(recipe["cuisine"], "American")
        self.assertEqual(recipe["tags"], ["quick", "dinner"])
        self.assertEqual(
            recipe["ingredients"],
            [{"quantity": 0.5, "unit": "cup", "name": "flour", "preparation": ""}],
        )
        self.assertEqual(recipe["steps"], [{"step_number": 1, "instruction": "Mix."}])

    def test_quantity_parser_handles_fraction_edge_cases(self):
        self.assertEqual(_parse_quantity("1 1/2"), 1.5)
        self.assertEqual(_parse_quantity("1/4"), 0.25)
        self.assertEqual(_parse_quantity("½"), 0.5)
        self.assertEqual(_parse_quantity("about 1"), 1.0)


class IngestUrlEndpointTests(unittest.TestCase):
    def test_ingest_url_inserts_recipe_ingredients_and_steps(self):
        with TemporaryDirectory() as tmp:
            previous_database_url = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = str(Path(tmp) / "recipes.db")
            try:
                import backend.db as db_module
                import backend.main as main_module

                db_module._db = None
                main_module = importlib.reload(main_module)

                async def fake_scrape_url(url: str) -> dict:
                    return {
                        "title": "Smoke Test Recipe",
                        "source_url": url,
                        "servings": 4,
                        "prep_min": 10,
                        "cook_min": 20,
                        "cuisine": "Test",
                        "tags": ["dinner"],
                        "ingredients": [
                            {
                                "quantity": 1.5,
                                "unit": "cups",
                                "name": "flour",
                                "preparation": "",
                            }
                        ],
                        "steps": [{"step_number": 1, "instruction": "Mix."}],
                        "source": "recipe-scrapers",
                    }

                main_module.scrape_url = fake_scrape_url
                response = TestClient(main_module.app).post(
                    "/api/recipes/url",
                    json={"url": "https://example.com/recipe"},
                )

                self.assertEqual(response.status_code, 201, response.text)
                body = response.json()
                self.assertEqual(body["title"], "Smoke Test Recipe")
                self.assertEqual(body["source"], "recipe-scrapers")

                db_module._db = None
                db = db_module.get_db()
                self.assertEqual(db["recipes"].count, 1)
                self.assertEqual(db["ingredients"].count, 1)
                self.assertEqual(db["steps"].count, 1)
                self.assertEqual(db["recipes"].get(1)["title"], "Smoke Test Recipe")
                self.assertEqual(db["ingredients"].get(1)["name"], "flour")
                self.assertEqual(db["steps"].get(1)["instruction"], "Mix.")
            finally:
                import backend.db as db_module

                db_module._db = None
                if previous_database_url is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = previous_database_url


if __name__ == "__main__":
    unittest.main()

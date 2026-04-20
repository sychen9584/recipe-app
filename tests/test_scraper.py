from backend.scraper import normalise_claude, _parse_quantity, _try_recipe_scrapers_html


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


def test_recipe_scrapers_html_normalizes_schema_recipe():
    recipe = _try_recipe_scrapers_html(RECIPE_SCHEMA_HTML, "https://example.com/test")

    assert recipe is not None
    assert recipe["title"] == "Test Pancakes"
    assert recipe["source_url"] == "https://example.com/test"
    assert recipe["servings"] == 4
    assert recipe["prep_min"] == 10
    assert recipe["cook_min"] == 15
    assert recipe["cuisine"] == "American"
    assert recipe["tags"] == ["breakfast", "pancakes"]
    assert recipe["ingredients"][0] == {
        "quantity": 1.5,
        "unit": "cups",
        "name": "flour",
        "preparation": "",
    }
    assert recipe["steps"] == [
        {"step_number": 1, "instruction": "Mix ingredients."},
        {"step_number": 2, "instruction": "Cook on griddle."},
    ]


def test_claude_normalization_cleans_and_filters_payload():
    recipe = normalise_claude(
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

    assert recipe["title"] == "Test Recipe"
    assert recipe["servings"] == 4
    assert recipe["prep_min"] == 5
    assert recipe["cook_min"] == 10
    assert recipe["cuisine"] == "American"
    assert recipe["tags"] == ["quick", "dinner"]
    assert recipe["ingredients"] == [
        {"quantity": 0.5, "unit": "cup", "name": "flour", "preparation": ""}
    ]
    assert recipe["steps"] == [{"step_number": 1, "instruction": "Mix."}]


def test_quantity_parser_handles_fraction_edge_cases():
    assert _parse_quantity("1 1/2") == 1.5
    assert _parse_quantity("1/4") == 0.25
    assert _parse_quantity("½") == 0.5
    assert _parse_quantity("about 1") == 1.0


def test_ingest_url_inserts_recipe_ingredients_and_steps(app_context, client):
    main_module, db_module = app_context

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
    response = client.post(
        "/api/recipes/url",
        json={"url": "https://example.com/recipe"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Smoke Test Recipe"
    assert body["source"] == "recipe-scrapers"

    db = db_module.get_db()
    assert db["recipes"].count == 1
    assert db["ingredients"].count == 1
    assert db["steps"].count == 1
    assert db["recipes"].get(1)["title"] == "Smoke Test Recipe"
    assert db["ingredients"].get(1)["name"] == "flour"
    assert db["steps"].get(1)["instruction"] == "Mix."

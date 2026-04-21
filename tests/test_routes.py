def test_recipe_read_routes_and_delete(app_context, client):
    _, db_module = app_context
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

    list_response = client.get("/api/recipes")
    assert list_response.status_code == 200, list_response.text
    assert len(list_response.json()) == 2

    search_response = client.get("/api/recipes?q=lemon")
    assert search_response.status_code == 200, search_response.text
    assert [recipe["title"] for recipe in search_response.json()] == ["Lemon Pasta"]

    tag_search_response = client.get("/api/recipes?q=breakfast")
    assert tag_search_response.status_code == 200, tag_search_response.text
    assert [recipe["title"] for recipe in tag_search_response.json()] == ["Berry Smoothie"]

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


def test_delete_missing_recipe_returns_404(client):
    response = client.delete("/api/recipes/999")

    assert response.status_code == 404


def test_list_recipes_combines_search_and_exact_tag_filter(app_context, client):
    _, db_module = app_context
    db = db_module.get_db()
    db_module.insert_recipe(
        db,
        {
            "title": "Tomato Soup",
            "source_url": "https://example.com/tomato",
            "servings": 4,
            "prep_min": 10,
            "cook_min": 30,
            "cuisine": "American",
            "tags": ["weeknight", "soup"],
            "ingredients": [],
            "steps": [],
        },
    )
    db_module.insert_recipe(
        db,
        {
            "title": "Weekend Soup",
            "source_url": "https://example.com/weekend",
            "servings": 4,
            "prep_min": 10,
            "cook_min": 60,
            "cuisine": "American",
            "tags": ["weeknight-ish", "soup"],
            "ingredients": [],
            "steps": [],
        },
    )
    db_module.insert_recipe(
        db,
        {
            "title": "Weeknight Pasta",
            "source_url": "https://example.com/pasta",
            "servings": 4,
            "prep_min": 10,
            "cook_min": 20,
            "cuisine": "Italian",
            "tags": ["weeknight", "pasta"],
            "ingredients": [],
            "steps": [],
        },
    )

    exact_tag_response = client.get("/api/recipes?tag=weeknight")
    assert exact_tag_response.status_code == 200, exact_tag_response.text
    assert [recipe["title"] for recipe in exact_tag_response.json()] == [
        "Weeknight Pasta",
        "Tomato Soup",
    ]

    combined_response = client.get("/api/recipes?q=soup&tag=weeknight")
    assert combined_response.status_code == 200, combined_response.text
    assert [recipe["title"] for recipe in combined_response.json()] == ["Tomato Soup"]


def test_patch_recipe_updates_only_present_fields(app_context, client):
    _, db_module = app_context
    recipe_id = db_module.insert_recipe(
        db_module.get_db(),
        {
            "title": "Original Soup",
            "source_url": "https://example.com/soup",
            "servings": 4,
            "prep_min": 10,
            "cook_min": 25,
            "cuisine": "American",
            "tags": ["cozy", "dinner"],
            "ingredients": [
                {
                    "quantity": 1.0,
                    "unit": "cup",
                    "name": "stock",
                    "preparation": "",
                }
            ],
            "steps": [{"step_number": 1, "instruction": "Simmer."}],
        },
    )

    response = client.patch(
        f"/api/recipes/{recipe_id}",
        json={"title": "Better Soup", "cook_min": 45, "tags": ["updated", "test"]},
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["title"] == "Better Soup"
    assert updated["cook_min"] == 45
    assert updated["tags"] == ["updated", "test"]
    assert updated["cuisine"] == "American"
    assert updated["prep_min"] == 10
    assert updated["ingredients"][0]["name"] == "stock"
    assert updated["steps"][0]["instruction"] == "Simmer."


def test_patch_recipe_empty_body_returns_current_recipe(app_context, client):
    _, db_module = app_context
    recipe_id = db_module.insert_recipe(
        db_module.get_db(),
        {
            "title": "No Change",
            "source_url": "https://example.com/no-change",
            "servings": 2,
            "prep_min": 5,
            "cook_min": 8,
            "cuisine": "",
            "tags": ["quick"],
            "ingredients": [],
            "steps": [],
        },
    )

    response = client.patch(f"/api/recipes/{recipe_id}", json={})

    assert response.status_code == 200, response.text
    assert response.json()["title"] == "No Change"
    assert response.json()["tags"] == ["quick"]


def test_patch_recipe_can_delete_all_tags(app_context, client):
    _, db_module = app_context
    recipe_id = db_module.insert_recipe(
        db_module.get_db(),
        {
            "title": "Tagged Recipe",
            "source_url": "https://example.com/tagged",
            "servings": 2,
            "prep_min": 5,
            "cook_min": 8,
            "cuisine": "",
            "tags": ["old", "remove-me"],
            "ingredients": [],
            "steps": [],
        },
    )

    response = client.patch(f"/api/recipes/{recipe_id}", json={"tags": []})
    assert response.status_code == 200, response.text
    assert response.json()["tags"] == []

    detail_response = client.get(f"/api/recipes/{recipe_id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["tags"] == []


def test_patch_missing_recipe_returns_404(client):
    response = client.patch("/api/recipes/999", json={"title": "Missing"})

    assert response.status_code == 404


def test_patch_recipe_rejects_invalid_fields(app_context, client):
    _, db_module = app_context
    recipe_id = db_module.insert_recipe(
        db_module.get_db(),
        {
            "title": "Valid Recipe",
            "source_url": "https://example.com/valid",
            "servings": 1,
            "prep_min": 0,
            "cook_min": 0,
            "cuisine": "",
            "tags": [],
            "ingredients": [],
            "steps": [],
        },
    )

    invalid_payloads = [
        {"title": "  "},
        {"prep_min": -1},
        {"cook_min": -1},
        {"tags": ["ok", ""]},
    ]

    for payload in invalid_payloads:
        response = client.patch(f"/api/recipes/{recipe_id}", json=payload)
        assert response.status_code == 422, payload

import os
from types import SimpleNamespace

import pytest

import backend.parser as parser


class _FakeMessages:
    def create(self, **kwargs):
        self.kwargs = kwargs
        body = """
        ```json
        {
          "title": "Uploaded Recipe",
          "servings": "2 servings",
          "prep_min": "5 minutes",
          "cook_min": "12",
          "cuisine": "Test Kitchen",
          "tags": "upload, quick",
          "ingredients": [
            {"quantity": "1/2", "unit": "cup", "name": "flour", "preparation": ""}
          ],
          "steps": [
            {"step_number": 1, "instruction": "Mix."}
          ]
        }
        ```
        """
        return SimpleNamespace(
            stop_reason="end_turn",
            content=[SimpleNamespace(type="text", text=body)],
        )


class _FakeAnthropic:
    last_messages = None

    def __init__(self, api_key):
        self.api_key = api_key
        self.messages = _FakeMessages()
        type(self).last_messages = self.messages


@pytest.mark.anyio
async def test_parse_upload_rejects_unsupported_media_type():
    with pytest.raises(ValueError, match="Unsupported file type: text/plain"):
        await parser.parse_upload(b"recipe", "text/plain", "recipe.txt")


@pytest.mark.anyio
async def test_parse_upload_rejects_oversized_file():
    oversized = b"x" * (parser.MAX_UPLOAD_BYTES + 1)

    with pytest.raises(ValueError, match="Upload too large"):
        await parser.parse_upload(oversized, "image/jpeg", "large.jpg")


@pytest.mark.anyio
async def test_parse_upload_returns_normalised_recipe(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(parser, "Anthropic", _FakeAnthropic)

    recipe = await parser.parse_upload(b"fake image bytes", "image/png", "card.png")

    assert recipe["title"] == "Uploaded Recipe"
    assert recipe["source_url"] == "upload:card.png"
    assert recipe["source"] == "upload-image"
    assert recipe["servings"] == 2
    assert recipe["prep_min"] == 5
    assert recipe["cook_min"] == 12
    assert recipe["cuisine"] == "Test Kitchen"
    assert recipe["tags"] == ["upload", "quick"]
    assert recipe["ingredients"] == [
        {"quantity": 0.5, "unit": "cup", "name": "flour", "preparation": ""}
    ]
    assert recipe["steps"] == [{"step_number": 1, "instruction": "Mix."}]

    assert _FakeAnthropic.last_messages is not None
    content = _FakeAnthropic.last_messages.kwargs["messages"][0]["content"]
    assert content[0]["type"] == "image"
    assert content[0]["source"]["media_type"] == "image/png"
    assert _FakeAnthropic.last_messages.kwargs["max_tokens"] == parser.CLAUDE_MAX_TOKENS


def test_upload_endpoint_inserts_recipe(app_context, client):
    main_module, db_module = app_context

    async def fake_parse_upload(file_bytes, media_type, filename):
        assert file_bytes == b"fake-pdf"
        assert media_type == "application/pdf"
        assert filename == "recipe.pdf"
        return {
            "title": "Uploaded Recipe",
            "source_url": "upload:recipe.pdf",
            "servings": 4,
            "prep_min": 10,
            "cook_min": 20,
            "cuisine": "Test",
            "tags": ["upload"],
            "ingredients": [
                {
                    "quantity": 1.5,
                    "unit": "cups",
                    "name": "flour",
                    "preparation": "",
                }
            ],
            "steps": [{"step_number": 1, "instruction": "Mix."}],
            "source": "upload-pdf",
        }

    main_module.parse_upload = fake_parse_upload
    response = client.post(
        "/api/recipes/upload",
        files={"file": ("recipe.pdf", b"fake-pdf", "application/pdf")},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "Uploaded Recipe"
    assert body["source_url"] == "upload:recipe.pdf"
    assert body["source"] == "upload-pdf"

    db = db_module.get_db()
    assert db["recipes"].count == 1
    assert db["ingredients"].count == 1
    assert db["steps"].count == 1
    assert db["recipes"].get(1)["source_url"] == "upload:recipe.pdf"
    assert db["ingredients"].get(1)["name"] == "flour"
    assert db["steps"].get(1)["instruction"] == "Mix."


def test_upload_endpoint_rejects_unsupported_media_type(client):
    response = client.post(
        "/api/recipes/upload",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415


def test_upload_endpoint_rejects_oversized_file(client):
    response = client.post(
        "/api/recipes/upload",
        files={"file": ("large.jpg", b"x" * (parser.MAX_UPLOAD_BYTES + 1), "image/jpeg")},
    )

    assert response.status_code == 413

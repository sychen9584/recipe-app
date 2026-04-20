import importlib
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from fastapi.testclient import TestClient

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


class ParserTests(unittest.IsolatedAsyncioTestCase):
    async def test_parse_upload_rejects_unsupported_media_type(self):
        with self.assertRaisesRegex(ValueError, "Unsupported file type: text/plain"):
            await parser.parse_upload(b"recipe", "text/plain", "recipe.txt")

    async def test_parse_upload_rejects_oversized_file(self):
        oversized = b"x" * (parser.MAX_UPLOAD_BYTES + 1)

        with self.assertRaisesRegex(ValueError, "Upload too large"):
            await parser.parse_upload(oversized, "image/jpeg", "large.jpg")

    async def test_parse_upload_returns_normalised_recipe(self):
        previous_key = os.environ.get("ANTHROPIC_API_KEY")
        previous_client = parser.Anthropic
        os.environ["ANTHROPIC_API_KEY"] = "test-key"
        parser.Anthropic = _FakeAnthropic
        try:
            recipe = await parser.parse_upload(b"fake image bytes", "image/png", "card.png")
        finally:
            parser.Anthropic = previous_client
            if previous_key is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = previous_key

        self.assertEqual(recipe["title"], "Uploaded Recipe")
        self.assertEqual(recipe["source_url"], "upload:card.png")
        self.assertEqual(recipe["source"], "upload-image")
        self.assertEqual(recipe["servings"], 2)
        self.assertEqual(recipe["prep_min"], 5)
        self.assertEqual(recipe["cook_min"], 12)
        self.assertEqual(recipe["cuisine"], "Test Kitchen")
        self.assertEqual(recipe["tags"], ["upload", "quick"])
        self.assertEqual(
            recipe["ingredients"],
            [{"quantity": 0.5, "unit": "cup", "name": "flour", "preparation": ""}],
        )
        self.assertEqual(recipe["steps"], [{"step_number": 1, "instruction": "Mix."}])

        assert _FakeAnthropic.last_messages is not None
        content = _FakeAnthropic.last_messages.kwargs["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "image")
        self.assertEqual(content[0]["source"]["media_type"], "image/png")
        self.assertEqual(_FakeAnthropic.last_messages.kwargs["max_tokens"], parser.CLAUDE_MAX_TOKENS)


class UploadEndpointTests(unittest.TestCase):
    def test_upload_endpoint_inserts_recipe(self):
        with TemporaryDirectory() as tmp:
            previous_database_url = os.environ.get("DATABASE_URL")
            os.environ["DATABASE_URL"] = str(Path(tmp) / "recipes.db")
            try:
                import backend.db as db_module
                import backend.main as main_module

                db_module._db = None
                main_module = importlib.reload(main_module)

                async def fake_parse_upload(file_bytes, media_type, filename):
                    self.assertEqual(file_bytes, b"fake-pdf")
                    self.assertEqual(media_type, "application/pdf")
                    self.assertEqual(filename, "recipe.pdf")
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
                response = TestClient(main_module.app).post(
                    "/api/recipes/upload",
                    files={"file": ("recipe.pdf", b"fake-pdf", "application/pdf")},
                )

                self.assertEqual(response.status_code, 201, response.text)
                body = response.json()
                self.assertEqual(body["title"], "Uploaded Recipe")
                self.assertEqual(body["source_url"], "upload:recipe.pdf")
                self.assertEqual(body["source"], "upload-pdf")

                db_module._db = None
                db = db_module.get_db()
                self.assertEqual(db["recipes"].count, 1)
                self.assertEqual(db["ingredients"].count, 1)
                self.assertEqual(db["steps"].count, 1)
                self.assertEqual(db["recipes"].get(1)["source_url"], "upload:recipe.pdf")
                self.assertEqual(db["ingredients"].get(1)["name"], "flour")
                self.assertEqual(db["steps"].get(1)["instruction"], "Mix.")
            finally:
                import backend.db as db_module

                db_module._db = None
                if previous_database_url is None:
                    os.environ.pop("DATABASE_URL", None)
                else:
                    os.environ["DATABASE_URL"] = previous_database_url

    def test_upload_endpoint_rejects_unsupported_media_type(self):
        import backend.main as main_module

        response = TestClient(main_module.app).post(
            "/api/recipes/upload",
            files={"file": ("notes.txt", b"plain text", "text/plain")},
        )

        self.assertEqual(response.status_code, 415)

    def test_upload_endpoint_rejects_oversized_file(self):
        import backend.main as main_module

        response = TestClient(main_module.app).post(
            "/api/recipes/upload",
            files={"file": ("large.jpg", b"x" * (parser.MAX_UPLOAD_BYTES + 1), "image/jpeg")},
        )

        self.assertEqual(response.status_code, 413)


if __name__ == "__main__":
    unittest.main()

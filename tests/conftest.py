import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_context(tmp_path):
    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = str(Path(tmp_path) / "recipes.db")

    import backend.db as db_module
    import backend.main as main_module

    db_module._db = None
    main_module = importlib.reload(main_module)
    try:
        yield main_module, db_module
    finally:
        db_module._db = None
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@pytest.fixture
def client(app_context):
    main_module, _ = app_context
    return TestClient(main_module.app)

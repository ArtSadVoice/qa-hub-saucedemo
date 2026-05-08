"""Pytest config — makes _hub/app.py importable and provides Flask test_client."""
import sys
from pathlib import Path

# Add _hub dir to sys.path so `import app` works from tests/
HUB_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HUB_DIR))

import pytest
import app as hub_app  # noqa: E402


@pytest.fixture
def client():
    """Flask test_client — uses real HUB_DIR state (read-only assumptions)."""
    hub_app.app.config["TESTING"] = True
    with hub_app.app.test_client() as c:
        yield c


@pytest.fixture
def hub():
    """Return the hub_app module for direct helper access in unit tests."""
    return hub_app

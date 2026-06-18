"""Pytest configuration: sandbox data paths to tests/test_data/ for all test runs.

src.config now exposes env-controlled paths as functions (e.g. config.chroma_dir()),
so env vars can be set at any point before the function is called — no import-timing
race. The sandbox is applied inside _isolated_test_data_root (a session-scoped autouse
fixture) so it takes effect before any test function runs.
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest
from dotenv import load_dotenv

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Load API keys from the repo-root .env (some integration tests skipif on OPENAI_API_KEY).
load_dotenv(os.path.join(_REPO_ROOT, ".env"))

_TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), "test_data")


@pytest.fixture(scope="session", autouse=True)
def _isolated_test_data_root():
    """Redirect EAC_* paths to tests/test_data/ for the duration of the session."""
    os.environ["EAC_DOCS_DIR"] = os.path.join(_TEST_DATA_DIR, "docs")
    os.environ["EAC_DB_FILE"] = os.path.join(_TEST_DATA_DIR, "engineering_data.db")
    os.environ["EAC_CHROMA_DIR"] = os.path.join(_TEST_DATA_DIR, "chroma_db")

    if os.path.exists(_TEST_DATA_DIR):
        shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
    os.makedirs(_TEST_DATA_DIR, exist_ok=True)

    yield _TEST_DATA_DIR

    try:
        from src.agent import close_connections

        close_connections()
    except ImportError:
        pass
    except Exception as e:
        print(f"Error closing DB connections at teardown: {e}")

    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def built_test_data(_isolated_test_data_root):
    """Populate tests/test_data/ with mock docs, SQLite, and Chroma vectors.

    Use this fixture in integration tests that need a fully built corpus.
    Skipped automatically if OPENAI_API_KEY is missing (build step requires it).
    """
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        pytest.skip("OPENAI_API_KEY not set; skipping built corpus fixture.")

    from src.build_vector_db import build_vector_database
    from src.generate_mock_data import main as generate_main

    generate_main()
    build_vector_database()
    return _isolated_test_data_root

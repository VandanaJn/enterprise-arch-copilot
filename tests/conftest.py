import os
import sys

import pytest
from dotenv import load_dotenv

# Repo root is the parent of tests/ (where README.md and .env live).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Load before test modules import src.* (skip logic + LangChain). Repo-root .env only.
load_dotenv(os.path.join(_ROOT, ".env"))


@pytest.fixture(scope="session", autouse=True)
def close_agent_connections():
    """Ensure all database connections are closed after the test session."""
    yield
    try:
        from src.agent import close_connections

        close_connections()
    except ImportError:
        pass
    except Exception as e:
        print(f"Error during teardown: {e}")

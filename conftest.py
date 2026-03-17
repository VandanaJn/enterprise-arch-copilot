import pytest
import os
import sys

# Add root to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

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

"""One-command bootstrap for the Enterprise Architecture Copilot.

Run as:
    python -m scripts.setup

Validates the environment, generates mock data, and builds the vector DB.
Exits non-zero on any failure so it composes cleanly in Make targets and CI.
"""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


def _fail(message: str) -> None:
    print(f"\n[setup] ERROR: {message}\n", file=sys.stderr)
    sys.exit(1)


def _check_env() -> None:
    load_dotenv(os.path.join(REPO_ROOT, ".env"))
    key = os.getenv("OPENAI_API_KEY", "")
    if not key or key == "your_openai_api_key_here":
        _fail(
            "OPENAI_API_KEY is missing. Copy .env.example to .env and add your key:\n"
            "  cp .env.example .env"
        )


def main() -> None:
    print("[setup] 1/3  Validating environment...")
    _check_env()
    print("[setup]      OK")

    print("[setup] 2/3  Generating mock data (docs/ and engineering_data.db)...")
    from src.generate_mock_data import main as generate_mock_data

    generate_mock_data()

    print("[setup] 3/3  Building vector database (chroma_db/)...")
    from src.build_vector_db import build_vector_database

    build_vector_database()

    print("\n[setup] Ready. Run the copilot with:\n  python main.py\n")


if __name__ == "__main__":
    main()

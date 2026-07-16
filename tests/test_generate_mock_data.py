"""Unit tests for src.generate_mock_data.

All paths point under tests/test_data/ thanks to env vars set in conftest.py.
We still wipe the docs+db between tests so each starts from a clean slate.
"""

import os
import shutil
import sqlite3

import pytest

from src import config
from src.agent import close_connections
from src.config import DOC_SUBDIRS
from src.generate_mock_data import (
    create_directories,
    generate_structured_data,
    generate_unstructured_data,
)


@pytest.fixture(autouse=True)
def _clean_between_tests():
    """Reset isolated test_data corpus before/after each test."""
    close_connections()
    if os.path.exists(config.docs_dir()):
        shutil.rmtree(config.docs_dir(), ignore_errors=True)
    if os.path.exists(config.db_file()):
        os.remove(config.db_file())
    yield
    close_connections()
    if os.path.exists(config.docs_dir()):
        shutil.rmtree(config.docs_dir(), ignore_errors=True)
    if os.path.exists(config.db_file()):
        os.remove(config.db_file())


def test_create_directories():
    create_directories()
    for sub in DOC_SUBDIRS:
        assert os.path.exists(os.path.join(config.docs_dir(), sub)), f"missing subdir: {sub}"


def test_generate_unstructured_data_copies_all_subdirs():
    create_directories()
    generate_unstructured_data()
    # Each subdirectory should contain at least one .md file copied from templates/.
    for sub in DOC_SUBDIRS:
        files = [f for f in os.listdir(os.path.join(config.docs_dir(), sub)) if f.endswith(".md")]
        assert files, f"no markdown copied into {sub}"


def test_generate_structured_data_seeds_all_tables():
    generate_structured_data()
    assert os.path.exists(config.db_file())

    conn = sqlite3.connect(config.db_file())
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT count(*) FROM service_catalog")
        services = cursor.fetchone()[0]
        assert services >= 8, f"expected >=8 services, got {services}"

        cursor.execute("SELECT count(*) FROM api_endpoints")
        endpoints = cursor.fetchone()[0]
        assert endpoints >= 20, f"expected >=20 endpoints, got {endpoints}"

        cursor.execute("SELECT count(*) FROM incidents")
        incidents = cursor.fetchone()[0]
        assert incidents >= 10, f"expected >=10 incidents, got {incidents}"

        # Spot-check a known service from the spec
        cursor.execute(
            "SELECT owner_team, criticality_tier FROM service_catalog WHERE name = 'checkout-service'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == "tier-0"

        # Spot-check that at least one incident links to a postmortem
        cursor.execute("SELECT count(*) FROM incidents WHERE postmortem_id IS NOT NULL")
        with_pm = cursor.fetchone()[0]
        assert with_pm >= 5
    finally:
        conn.close()

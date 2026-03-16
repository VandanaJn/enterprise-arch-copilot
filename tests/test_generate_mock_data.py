import os
import sqlite3
import pytest
from src.generate_mock_data import generate_unstructured_data, generate_structured_data, create_directories, DOCS_DIR, ADR_DIR, RUNBOOK_DIR, DB_FILE
import shutil

@pytest.fixture(autouse=True)
def cleanup():
    """Cleanup before and after each test."""
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    yield
    # Teardown
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

def test_create_directories():
    """Test that the required directories are created successfully."""
    create_directories()
    assert os.path.exists(ADR_DIR)
    assert os.path.exists(RUNBOOK_DIR)

def test_generate_unstructured_data():
    """Test that mock markdown files are generated correctly."""
    create_directories()
    generate_unstructured_data()
    
    # Check if ADRs were created
    assert os.path.exists(os.path.join(ADR_DIR, "001-use-kafka-for-events.md"))
    assert os.path.exists(os.path.join(ADR_DIR, "002-migrate-checkout-to-aws.md"))
    
    # Check if runbooks were created
    assert os.path.exists(os.path.join(RUNBOOK_DIR, "checkout-service-504-mitigation.md"))
    assert os.path.exists(os.path.join(RUNBOOK_DIR, "user-profile-db-failover.md"))

def test_generate_structured_data():
    """Test that the SQLite database is created and populated."""
    generate_structured_data()
    assert os.path.exists(DB_FILE)
    
    # Connect and verify data
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check service_catalog table
    cursor.execute("SELECT count(*) FROM service_catalog")
    service_count = cursor.fetchone()[0]
    assert service_count == 3
    
    # Check api_endpoints table
    cursor.execute("SELECT count(*) FROM api_endpoints")
    endpoint_count = cursor.fetchone()[0]
    assert endpoint_count == 4
    
    conn.close()

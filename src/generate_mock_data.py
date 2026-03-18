import os
import sqlite3
import json

# Get the absolute root directory of the project (one level up from src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define directories for unstructured data
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
ADR_DIR = os.path.join(DOCS_DIR, "adrs")
RUNBOOK_DIR = os.path.join(DOCS_DIR, "runbooks")
TEMPLATES_DIR = os.path.join(ROOT_DIR, "templates", "mock_docs")
DB_FILE = os.path.join(ROOT_DIR, "engineering_data.db")

def create_directories():
    """Create the necessary directory structure for Markdown docs."""
    for directory in [ADR_DIR, RUNBOOK_DIR]:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

def generate_unstructured_data():
    """Generate mock Markdown Architecture Decision Records and Runbooks from templates."""
    
    doc_types = ["adrs", "runbooks"]
    
    for doc_type in doc_types:
        source_dir = os.path.join(TEMPLATES_DIR, doc_type)
        target_dir = os.path.join(DOCS_DIR, doc_type)
        
        if not os.path.exists(source_dir):
            print(f"⚠️ Warning: Template directory '{source_dir}' not found. Skipping {doc_type}.")
            continue
            
        print(f"Generating {doc_type} from templates...")
        for filename in os.listdir(source_dir):
            if filename.endswith(".md"):
                source_path = os.path.join(source_dir, filename)
                target_path = os.path.join(target_dir, filename)
                
                with open(source_path, "r", encoding="utf-8") as f_src:
                    content = f_src.read()
                    
                with open(target_path, "w", encoding="utf-8") as f_dest:
                    f_dest.write(content)
                print(f"  [OK] Generated: {target_path}")

def generate_structured_data():
    """Generate a local SQLite database with Service Catalog and API Endpoints."""
    # Connect to SQLite (this creates the file if it doesn't exist)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create Tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS service_catalog (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        owner_team TEXT NOT NULL,
        version TEXT NOT NULL,
        oncall_rotation TEXT NOT NULL,
        repository_url TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS api_endpoints (
        id INTEGER PRIMARY KEY,
        path TEXT NOT NULL,
        service_id INTEGER NOT NULL,
        method TEXT NOT NULL,
        description TEXT,
        FOREIGN KEY (service_id) REFERENCES service_catalog (id)
    )
    ''')

    # Clear existing data just in case this is run multiple times
    cursor.execute('DELETE FROM api_endpoints')
    cursor.execute('DELETE FROM service_catalog')

    # Insert Data into service_catalog
    services = [
        (1, 'checkout-service', 'Team Alpha', 'v1.4.2', 'pagerduty-alpha', 'github.com/org/checkout-service'),
        (2, 'user-profile-service', 'Team Beta', 'v2.1.0', 'pagerduty-beta', 'github.com/org/user-profile-service'),
        (3, 'inventory-service', 'Team Gamma', 'v1.0.5', 'pagerduty-gamma', 'github.com/org/inventory-service')
    ]
    cursor.executemany('''
        INSERT INTO service_catalog (id, name, owner_team, version, oncall_rotation, repository_url)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', services)

    # Insert Data into api_endpoints
    endpoints = [
        (1, '/api/v1/checkout', 1, 'POST', 'Processes a new order checkout'),
        (2, '/api/v1/checkout/status', 1, 'GET', 'Gets the status of an existing checkout'),
        (3, '/api/v1/users/profile', 2, 'GET', 'Retrieves user profile information'),
        (4, '/api/v1/inventory/check', 3, 'POST', 'Checks if items are in stock')
    ]
    cursor.executemany('''
        INSERT INTO api_endpoints (id, path, service_id, method, description)
        VALUES (?, ?, ?, ?, ?)
    ''', endpoints)

    conn.commit()
    conn.close()
    print(f"Generated structured database: {DB_FILE} with service_catalog and api_endpoints tables.")

if __name__ == "__main__":
    print("Starting mock data generation...")
    create_directories()
    generate_unstructured_data()
    generate_structured_data()
    print("Mock data generation complete!")

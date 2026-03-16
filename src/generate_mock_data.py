import os
import sqlite3
import json

# Get the absolute root directory of the project (one level up from src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Define directories for unstructured data
DOCS_DIR = os.path.join(ROOT_DIR, "docs")
ADR_DIR = os.path.join(DOCS_DIR, "adrs")
RUNBOOK_DIR = os.path.join(DOCS_DIR, "runbooks")
DB_FILE = os.path.join(ROOT_DIR, "engineering_data.db")

def create_directories():
    """Create the necessary directory structure for Markdown docs."""
    for directory in [ADR_DIR, RUNBOOK_DIR]:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")

def generate_unstructured_data():
    """Generate mock Markdown Architecture Decision Records and Runbooks."""
    adrs = {
        "001-use-kafka-for-events.md": """# ADR 001: Use Kafka for Event Streaming
        
**Status:** Accepted
**Date:** 2023-10-15

## Context
Our monolithic architecture is struggling to handle the volume of checkout processing. We need a robust way to decouple services. RabbitMQ was considered but rejected due to throughput limitations.

## Decision
We will use Apache Kafka as our primary event streaming platform. The `checkout-service` will publish `OrderPlaced` events to the `checkout.events` topic. Downstream services like `inventory-service` and `notification-service` will subscribe to this topic.

## Consequences
- Better isolation between the checkout flow and downstream processing.
- Increased operational complexity (need to manage Kafka clusters).
""",
        "002-migrate-checkout-to-aws.md": """# ADR 002: Migrate Checkout Service to AWS EKS
        
**Status:** Accepted
**Date:** 2024-01-10

## Context
The `checkout-service` requires high elasticity during peak holiday shopping.

## Decision
We will migrate the `checkout-service` from on-premise VMs to AWS Elastic Kubernetes Service (EKS).

## Consequences
- Faster auto-scaling during traffic spikes.
- Requires team training on Kubernetes deployment manifests.
"""
    }

    runbooks = {
        "checkout-service-504-mitigation.md": """# Runbook: Checkout Service 504 Gateway Timeout

## Symptoms
- Datadog alerts show spike in 504 errors on the API Gateway for the `/api/v1/checkout` route.
- Customers report inability to complete purchases.

## Diagnostic Steps
1. Verify if the `checkout-service` pods are crashing in EKS using `kubectl get pods -n checkout`.
2. Check the connection to the primary PostgreSQL database. 
3. Verify if Kafka publisher is blocking.

## Mitigation
1. If pods are crash-looping due to memory, immediately scale up the deployment: 
   `kubectl scale deployment checkout-service --replicas=10 -n checkout`
2. If database connection is exhausted, restart the connection pooler.
3. Page the `Team Alpha` on-call if the issue persists after 5 minutes.
""",
        "user-profile-db-failover.md": """# Runbook: User Profile DB Failover

## Symptoms
- Read latency on `user-profile-service` exceeds 500ms.

## Mitigation
1. Manually promote the read-replica to primary in the AWS RDS Console.
2. Update the `DB_HOST` secret in AWS Secrets Manager.
3. Perform a rolling restart of the `user-profile-service` pods.
"""
    }

    # Write ADRs
    for filename, content in adrs.items():
        filepath = os.path.join(ADR_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated ADR: {filepath}")

    # Write Runbooks
    for filename, content in runbooks.items():
        filepath = os.path.join(RUNBOOK_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Generated Runbook: {filepath}")

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

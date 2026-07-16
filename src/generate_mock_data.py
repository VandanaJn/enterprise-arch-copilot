"""Seed the structured database and copy markdown templates into the docs/ tree.

The fictional company spec in templates/company_spec.md is the source of truth for
service names, teams, and tech stack. The seeds below mirror that spec; if you edit
the spec, update both this module and the LLM-generated corpus.
"""

import os
import sqlite3

from src import config
from src.config import DOC_SUBDIRS, TEMPLATES_DIR


def create_directories() -> None:
    """Create the markdown subdirectories under docs_dir."""
    for subdir in DOC_SUBDIRS:
        path = os.path.join(config.docs_dir(), subdir)
        os.makedirs(path, exist_ok=True)
        print(f"Created directory: {path}")


def generate_unstructured_data() -> None:
    """Copy markdown templates into the docs/ tree for ingestion."""
    for doc_type in DOC_SUBDIRS:
        source_dir = os.path.join(TEMPLATES_DIR, doc_type)
        target_dir = os.path.join(config.docs_dir(), doc_type)

        if not os.path.exists(source_dir):
            print(f"⚠️  Template directory '{source_dir}' not found. Skipping {doc_type}.")
            continue

        copied = 0
        for filename in os.listdir(source_dir):
            if not filename.endswith(".md"):
                continue
            source_path = os.path.join(source_dir, filename)
            target_path = os.path.join(target_dir, filename)
            with open(source_path, encoding="utf-8") as f_src:
                content = f_src.read()
            with open(target_path, "w", encoding="utf-8") as f_dest:
                f_dest.write(content)
            copied += 1
        print(f"  [OK] {doc_type}: copied {copied} file(s)")


# --- Structured seed data (mirrors templates/company_spec.md) ------------------

SERVICES: list[tuple] = [
    # (id, name, owner_team, version, oncall_rotation, repository_url, criticality_tier, deprecated, language)
    (
        1,
        "checkout-service",
        "Team Alpha",
        "v3.2.0",
        "pagerduty-alpha",
        "github.com/paylane/checkout-service",
        "tier-0",
        0,
        "Go",
    ),
    (
        2,
        "payment-gateway-service",
        "Team Alpha",
        "v2.4.1",
        "pagerduty-alpha",
        "github.com/paylane/payment-gateway-service",
        "tier-0",
        0,
        "Go",
    ),
    (
        3,
        "fraud-detection-service",
        "Team Sigma",
        "v1.7.3",
        "pagerduty-sigma",
        "github.com/paylane/fraud-detection-service",
        "tier-0",
        0,
        "Python",
    ),
    (
        4,
        "ledger-service",
        "Team Sigma",
        "v2.0.0",
        "pagerduty-sigma",
        "github.com/paylane/ledger-service",
        "tier-0",
        0,
        "Kotlin",
    ),
    (
        5,
        "user-profile-service",
        "Team Beta",
        "v2.5.2",
        "pagerduty-beta",
        "github.com/paylane/user-profile-service",
        "tier-1",
        0,
        "Python",
    ),
    (
        6,
        "notification-service",
        "Team Beta",
        "v1.3.0",
        "pagerduty-beta",
        "github.com/paylane/notification-service",
        "tier-1",
        0,
        "Python",
    ),
    (
        7,
        "webhook-dispatcher",
        "Team Beta",
        "v1.0.0",
        "pagerduty-beta",
        "github.com/paylane/webhook-dispatcher",
        "tier-1",
        0,
        "Go",
    ),
    (
        8,
        "merchant-onboarding-service",
        "Team Delta",
        "v1.8.1",
        "pagerduty-delta",
        "github.com/paylane/merchant-onboarding-service",
        "tier-2",
        0,
        "TypeScript",
    ),
    (
        9,
        "reporting-service",
        "Team Delta",
        "v1.4.0",
        "pagerduty-delta",
        "github.com/paylane/reporting-service",
        "tier-2",
        0,
        "Python",
    ),
    (
        10,
        "legacy-inventory-service",
        "Team Gamma",
        "v0.9.7",
        "pagerduty-gamma",
        "github.com/paylane/legacy-inventory-service",
        "tier-2",
        1,
        "Go",
    ),
]

ENDPOINTS: list[tuple] = [
    # (id, path, service_id, method, description)
    (1, "/api/v1/checkout", 1, "POST", "Create a new checkout session"),
    (2, "/api/v1/checkout/{id}/status", 1, "GET", "Poll the status of an existing checkout"),
    (3, "/api/v1/checkout/{id}/cancel", 1, "POST", "Cancel a pending checkout"),
    (4, "/api/v1/payments/authorize", 2, "POST", "Authorize a card for a checkout amount"),
    (5, "/api/v1/payments/capture", 2, "POST", "Capture a previously authorized payment"),
    (6, "/api/v1/payments/refund", 2, "POST", "Refund a captured payment"),
    (7, "/api/v1/payments/{id}", 2, "GET", "Retrieve a payment record"),
    (8, "/api/v1/fraud/score", 3, "POST", "Score a transaction for fraud risk"),
    (
        9,
        "/api/v1/fraud/feedback",
        3,
        "POST",
        "Submit chargeback or fraud-confirmation feedback for retraining",
    ),
    (10, "/api/v1/ledger/entries", 4, "GET", "Read ledger entries by account"),
    (11, "/api/v1/ledger/post", 4, "POST", "Post a double-entry ledger transaction"),
    (12, "/api/v1/users", 5, "POST", "Create a buyer account"),
    (13, "/api/v1/users/profile", 5, "GET", "Retrieve a buyer's profile"),
    (14, "/api/v1/users/profile", 5, "PUT", "Update a buyer's profile"),
    (15, "/api/v1/notifications/send", 6, "POST", "Send a transactional email or SMS"),
    (16, "/api/v1/notifications/{id}", 6, "GET", "Retrieve a notification status"),
    (17, "/api/v1/webhooks/dispatch", 7, "POST", "Dispatch an outbound webhook to a merchant"),
    (18, "/api/v1/webhooks/retry", 7, "POST", "Force a retry of a failed webhook delivery"),
    (19, "/api/v1/merchants/onboard", 8, "POST", "Begin merchant KYC onboarding"),
    (20, "/api/v1/merchants/{id}/status", 8, "GET", "Retrieve KYC status for a merchant"),
    (21, "/api/v1/reports/transactions", 9, "GET", "Fetch a transactions report (CSV/JSON)"),
    (22, "/api/v1/reports/settlements", 9, "GET", "Fetch a settlement report"),
    (23, "/api/v1/inventory/check", 10, "GET", "DEPRECATED — stock check (legacy commerce era)"),
    (
        24,
        "/api/v1/inventory/reserve",
        10,
        "POST",
        "DEPRECATED — reserve stock (legacy commerce era)",
    ),
]

# Historical incidents — some link to postmortems generated under templates/mock_docs/postmortems/.
INCIDENTS: list[tuple] = [
    # (id, service_id, started_at, ended_at, severity, summary, postmortem_id)
    (
        1,
        1,
        "2024-11-29 13:14:00",
        "2024-11-29 14:42:00",
        "SEV-1",
        "Black Friday checkout 504 spike during peak traffic",
        "PM-2024-001",
    ),
    (
        2,
        2,
        "2024-07-22 09:08:00",
        "2024-07-22 10:27:00",
        "SEV-2",
        "Payment-gateway-service authorization failures after Stripe credential rotation",
        "PM-2024-002",
    ),
    (
        3,
        3,
        "2024-05-14 16:00:00",
        "2024-05-15 02:00:00",
        "SEV-2",
        "Fraud model v1.7 regression — false positives on legitimate transactions",
        "PM-2024-003",
    ),
    (
        4,
        1,
        "2024-09-03 11:30:00",
        "2024-09-03 11:45:00",
        "SEV-3",
        "Kafka rebalance storm on checkout.events caused 5-minute consumer pause",
        "PM-2024-004",
    ),
    (
        5,
        7,
        "2024-08-19 22:01:00",
        "2024-08-20 00:30:00",
        "SEV-2",
        "Single merchant flooded webhook-dispatcher; queue saturation",
        "PM-2024-005",
    ),
    (
        6,
        4,
        "2024-06-11 04:30:00",
        "2024-06-11 09:15:00",
        "SEV-1",
        "Currency rounding bug — half-cent truncation impacted EU merchants",
        "PM-2024-006",
    ),
    (
        7,
        1,
        "2024-10-04 18:22:00",
        "2024-10-04 18:55:00",
        "SEV-2",
        "EKS deploy wedged the cluster; misconfigured pod disruption budget",
        "PM-2024-007",
    ),
    (
        8,
        4,
        "2024-03-28 12:00:00",
        "2024-03-28 19:00:00",
        "SEV-1",
        "Ledger double-entry bug — settlement drift over 7 hours",
        "PM-2024-008",
    ),
    # Incidents without postmortems (recent or low-sev)
    (
        9,
        5,
        "2025-02-12 03:20:00",
        "2025-02-12 03:40:00",
        "SEV-3",
        "user-profile-service latency spike during read-replica failover test",
        None,
    ),
    (
        10,
        6,
        "2025-01-30 14:10:00",
        "2025-01-30 14:25:00",
        "SEV-3",
        "notification-service Redis OOM during email blast",
        None,
    ),
    (
        11,
        9,
        "2025-01-08 10:00:00",
        "2025-01-08 11:30:00",
        "SEV-3",
        "reporting-service ClickHouse slow queries blocking dashboards",
        None,
    ),
    (
        12,
        8,
        "2024-12-19 09:45:00",
        "2024-12-19 10:12:00",
        "SEV-3",
        "merchant-onboarding-service stuck applications in KYC review",
        None,
    ),
    (
        13,
        2,
        "2024-12-02 21:00:00",
        "2024-12-02 21:18:00",
        "SEV-3",
        "TLS certificate near-expiry alert on api.paylane.io",
        None,
    ),
    (
        14,
        5,
        "2024-11-15 08:30:00",
        "2024-11-15 09:00:00",
        "SEV-3",
        "RDS connection pool exhaustion on user-profile",
        None,
    ),
    (
        15,
        1,
        "2024-10-30 23:00:00",
        "2024-10-30 23:35:00",
        "SEV-3",
        "ArgoCD rolled back a bad checkout-service deploy",
        None,
    ),
]


def generate_structured_data() -> None:
    """Create and populate the SQLite database from the seeds above."""
    conn = sqlite3.connect(config.db_file())
    cursor = conn.cursor()

    cursor.executescript(
        """
        DROP TABLE IF EXISTS incidents;
        DROP TABLE IF EXISTS api_endpoints;
        DROP TABLE IF EXISTS service_catalog;

        CREATE TABLE service_catalog (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            owner_team TEXT NOT NULL,
            version TEXT NOT NULL,
            oncall_rotation TEXT NOT NULL,
            repository_url TEXT,
            criticality_tier TEXT NOT NULL,
            deprecated INTEGER NOT NULL DEFAULT 0,
            language TEXT
        );

        CREATE TABLE api_endpoints (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL,
            service_id INTEGER NOT NULL,
            method TEXT NOT NULL,
            description TEXT,
            FOREIGN KEY (service_id) REFERENCES service_catalog (id)
        );

        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY,
            service_id INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            severity TEXT NOT NULL,
            summary TEXT NOT NULL,
            postmortem_id TEXT,
            FOREIGN KEY (service_id) REFERENCES service_catalog (id)
        );
        """
    )

    cursor.executemany(
        """INSERT INTO service_catalog
           (id, name, owner_team, version, oncall_rotation, repository_url, criticality_tier, deprecated, language)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        SERVICES,
    )
    cursor.executemany(
        "INSERT INTO api_endpoints (id, path, service_id, method, description) VALUES (?, ?, ?, ?, ?)",
        ENDPOINTS,
    )
    cursor.executemany(
        """INSERT INTO incidents
           (id, service_id, started_at, ended_at, severity, summary, postmortem_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        INCIDENTS,
    )

    conn.commit()
    conn.close()
    print(
        f"Generated SQLite at {config.db_file()}: "
        f"{len(SERVICES)} services, {len(ENDPOINTS)} endpoints, {len(INCIDENTS)} incidents."
    )


def main() -> None:
    """Generate all mock data (directories, markdown docs, SQLite DB)."""
    print("Starting mock data generation...")
    create_directories()
    generate_unstructured_data()
    generate_structured_data()
    print("Mock data generation complete!")


if __name__ == "__main__":
    main()

"""LLM-driven corpus generator for the Enterprise Architecture Copilot.

Generates ADRs, runbooks, postmortems, and design docs grounded in
templates/company_spec.md. Idempotent (skips existing files unless --force).

Examples:
    python -m scripts.generate_corpus --type adrs --count 25
    python -m scripts.generate_corpus --type runbooks --count 15
    python -m scripts.generate_corpus --type adrs --id ADR-007 --force
    python -m scripts.generate_corpus --type postmortems --count 8 --topic "Black Friday checkout outage"
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

SPEC_PATH = REPO_ROOT / "templates" / "company_spec.md"
CORPUS_ROOT = REPO_ROOT / "templates" / "mock_docs"


# --- Doc type configuration ----------------------------------------------------

class DocTypeConfig(BaseModel):
    prefix: str          # ID prefix, e.g. "ADR"
    dir_name: str        # subdir under templates/mock_docs
    structure_hint: str  # body section guidance
    topic_pool: list[str]


DOC_TYPES: dict[str, DocTypeConfig] = {
    "adrs": DocTypeConfig(
        prefix="ADR",
        dir_name="adrs",
        structure_hint=(
            "Use sections: ## Context, ## Decision, ## Consequences (with positive and negative bullets), "
            "and ## Alternatives Considered (with one-line rejection reason for each)."
        ),
        topic_pool=[
            "Adopt Kafka for event streaming (supersedes RabbitMQ choice)",
            "Use RabbitMQ for inter-service messaging (early decision; later superseded by Kafka)",
            "Service decomposition strategy (extract checkout from monolith)",
            "Migrate checkout-service to AWS EKS",
            "Standardize on Go for new tier-0 services",
            "Use Python for ML and data services",
            "Use Kotlin for ledger-service rewrite",
            "Adopt Datadog as primary metrics + APM platform",
            "Use Loki for centralized logs",
            "ArgoCD for EKS GitOps deploys",
            "Secret management via AWS KMS + Secrets Manager",
            "PCI-DSS network segmentation strategy",
            "Sunset legacy-inventory-service (deprecation plan)",
            "Adopt schema registry for Kafka topics",
            "Idempotency keys for payment-gateway endpoints",
            "Webhook retry semantics with exponential backoff",
            "Contract testing with Pact between services",
            "Blue/green deployments for tier-0 services",
            "Feature flag vendor selection (LaunchDarkly)",
            "API versioning strategy (path-based v1, v2)",
            "Rate limiting at the edge (CloudFront + API Gateway)",
            "Error budget policy and on-call escalation",
            "Postmortem process formalization (blameless template)",
            "Multi-region active-passive disaster recovery",
            "TimescaleDB choice for ledger time-series data",
            "ClickHouse choice for reporting-service analytics",
            "MongoDB choice for merchant-onboarding-service",
            "Redis as the primary cache layer",
            "Webhook dispatcher rewrite from Python to Go for throughput",
        ],
    ),
    "runbooks": DocTypeConfig(
        prefix="RB",
        dir_name="runbooks",
        structure_hint=(
            "Use sections: ## Symptoms, ## Diagnostic Steps (numbered), ## Mitigation (numbered), "
            "## Verification (how to confirm fix), ## Escalation (who to page if X minutes elapse)."
        ),
        topic_pool=[
            "checkout-service 504 gateway timeout mitigation",
            "payment-gateway-service authorization timeouts",
            "fraud-detection-service model fallback when ML cluster is down",
            "ledger-service reconciliation drift between TimescaleDB and Postgres",
            "user-profile-service RDS failover to read-replica",
            "Kafka consumer lag spike on checkout.events topic",
            "webhook-dispatcher backlog overflowing Redis",
            "merchant-onboarding-service stuck applications in KYC review",
            "reporting-service ClickHouse slow queries blocking dashboards",
            "EKS pod evictions on tier-0 nodes due to memory pressure",
            "RDS connection pool exhaustion on user-profile",
            "Redis memory pressure on notification-service",
            "TLS certificate expiry on api.paylane.io",
            "Emergency secrets rotation after suspected leak",
            "Production deploy rollback via ArgoCD",
        ],
    ),
    "postmortems": DocTypeConfig(
        prefix="PM",
        dir_name="postmortems",
        structure_hint=(
            "Use sections: ## Summary (1-2 sentences), ## Impact (customer-visible effects, duration, severity), "
            "## Timeline (UTC timestamps + actions), ## Root Cause, ## What Went Well, ## What Went Wrong, "
            "## Action Items (each with owner team and due quarter). Tone: blameless, factual."
        ),
        topic_pool=[
            "Black Friday 2024 checkout-service outage during peak traffic",
            "payment-gateway-service Stripe credential rotation incident",
            "fraud-detection-service v1.7 model regression flagging legitimate transactions",
            "ledger-service double-entry bug causing settlement drift",
            "Kafka rebalance storm on checkout.events triggering 5-minute consumer pause",
            "Single merchant DDOS via webhook flood saturating webhook-dispatcher",
            "EKS deploy that wedged the cluster via misconfigured pod disruption budget",
            "Currency rounding incident: half-cent truncation impacting EU merchants",
        ],
    ),
    "design_docs": DocTypeConfig(
        prefix="DD",
        dir_name="design_docs",
        structure_hint=(
            "Use sections: ## Goal, ## Non-Goals, ## Proposal (architecture overview), "
            "## API / Schema Changes, ## Migration Plan (phased), ## Risks, ## Open Questions."
        ),
        topic_pool=[
            "Migrate webhook-dispatcher from Python to Go",
            "Fraud-detection-service v2 architecture with online feature store",
            "Multi-region active-active for checkout-service",
            "Sunset plan for legacy-inventory-service",
            "Observability v2: adopt OpenTelemetry across all services",
        ],
    ),
}


# --- Pydantic schema for structured output -------------------------------------

class DocFrontmatter(BaseModel):
    id: str = Field(..., description="ID like ADR-007 / RB-012 / PM-2024-003 / DD-002. Must match the requested ID.")
    title: str = Field(..., description="Short title, sentence case, no leading article")
    status: str = Field(..., description="One of: Proposed, Accepted, Deprecated, Superseded")
    date: str = Field(..., description="ISO date YYYY-MM-DD; must be plausible given the engineering timeline")
    authors: list[str] = Field(..., description="Owning team handles like 'team-alpha'")
    services: list[str] = Field(..., description="Service names from the catalog this doc references")
    supersedes: list[str] = Field(default_factory=list, description="IDs this replaces, if any")
    superseded_by: Optional[str] = Field(default=None, description="ID that replaced this one, if any")
    related_to: list[str] = Field(default_factory=list, description="Related doc IDs (other ADRs / runbooks / postmortems)")


class GeneratedDoc(BaseModel):
    frontmatter: DocFrontmatter
    slug: str = Field(..., description="kebab-case filename slug, 3-6 words, no extension")
    body_markdown: str = Field(..., description="Markdown body. Do NOT include the YAML frontmatter or top-level # title heading.")


# --- Generation prompt assembly ------------------------------------------------

SYSTEM_PROMPT = """You are an experienced staff engineer at PayLane writing internal engineering documents (ADRs, runbooks, postmortems, design docs). Your writing is concrete, technical, and grounded in the company spec provided. You never invent services, teams, dates, or technologies that contradict the spec.

Tone: factual, blameless, decision-focused. Avoid corporate jargon. Use present tense for current state. Use specific service names from the catalog. Reference real metrics, error codes, and tools (Datadog, PagerDuty, Kafka topics named like `checkout.events`).

When asked to generate a document, return it via the structured-output schema. The body should be 200-500 words for runbooks and 400-900 words for ADRs/postmortems/design docs. Cross-reference other documents by ID where it makes sense (e.g. "see ADR-007 for the Kafka adoption rationale")."""


def _build_user_prompt(
    spec_text: str,
    doc_type: str,
    cfg: DocTypeConfig,
    requested_id: str,
    topic: Optional[str],
    existing_docs_summary: str,
) -> str:
    return f"""## Company spec (single source of truth)

{spec_text}

## Existing documents in this corpus

{existing_docs_summary or "(none yet)"}

## Task

Generate ONE {doc_type[:-1]} document with ID **{requested_id}**.

Topic / subject: **{topic or "pick from the topic pool below; do not duplicate any existing doc"}**.

Topic pool (for variety; pick one not yet covered if topic is unspecified):
{chr(10).join("- " + t for t in cfg.topic_pool)}

## Required structure for the body

{cfg.structure_hint}

## Frontmatter rules

- `id` MUST be exactly `{requested_id}`.
- `date` must be a real date that fits the engineering timeline (use 2020-2025 range).
- For supersession: if writing a doc that supersedes an earlier one (e.g. Kafka adopting after RabbitMQ), set `supersedes: [<earlier-id>]` AND ensure that earlier doc's `superseded_by` could plausibly point here. If the earlier doc already exists in the list above, prefer to supersede it; otherwise leave `supersedes` empty.
- `services` must be a subset of the service names from the catalog above.
- `authors` must be a subset of the team handles from the spec.
- `related_to` should reference real existing IDs from the list above when possible.

## Output

Return the document via the structured schema. Do NOT include the YAML `---` markers or a top-level `# title` heading inside `body_markdown` — the script writes those itself."""


# --- Filesystem helpers --------------------------------------------------------

ID_PATTERN = re.compile(r"^id:\s*(\S+)\s*$", re.MULTILINE)


def list_existing(doc_dir: Path) -> dict[str, Path]:
    """Map of doc ID -> file path for files in a corpus subdirectory."""
    if not doc_dir.exists():
        return {}
    out: dict[str, Path] = {}
    for f in doc_dir.glob("*.md"):
        try:
            head = f.read_text(encoding="utf-8")[:600]
            m = ID_PATTERN.search(head)
            if m:
                out[m.group(1)] = f
        except OSError:
            continue
    return out


def existing_summary(doc_dir: Path, max_items: int = 50) -> str:
    """Compact list of existing IDs + titles to feed back to the LLM as context."""
    if not doc_dir.exists():
        return ""
    rows: list[str] = []
    for f in sorted(doc_dir.glob("*.md")):
        try:
            text = f.read_text(encoding="utf-8")[:1000]
        except OSError:
            continue
        id_m = re.search(r"^id:\s*(\S+)", text, re.MULTILINE)
        title_m = re.search(r"^title:\s*(.+)$", text, re.MULTILINE)
        status_m = re.search(r"^status:\s*(\S+)", text, re.MULTILINE)
        if id_m and title_m:
            rows.append(
                f"- {id_m.group(1)} [{status_m.group(1) if status_m else '?'}]: {title_m.group(1).strip()}"
            )
        if len(rows) >= max_items:
            break
    return "\n".join(rows)


def next_id(existing_ids: set[str], prefix: str) -> str:
    """Find the next free ID. PM uses YYYY-NNN; others use NNN."""
    if prefix == "PM":
        # Most recent year wins; default 2024
        year = 2024
        used_for_year = {
            int(i.split("-")[2])
            for i in existing_ids
            if i.startswith(f"PM-{year}-")
        }
        n = 1
        while n in used_for_year:
            n += 1
        return f"PM-{year}-{n:03d}"
    used = {int(i.split("-")[1]) for i in existing_ids if i.startswith(f"{prefix}-")}
    n = 1
    while n in used:
        n += 1
    return f"{prefix}-{n:03d}"


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", s)[:60]


def render_markdown(doc: GeneratedDoc) -> str:
    """Compose the final .md content from structured fields."""
    fm = doc.frontmatter
    lines = ["---", f"id: {fm.id}", f"title: {fm.title}", f"status: {fm.status}", f"date: {fm.date}"]
    lines.append(f"authors: [{', '.join(fm.authors)}]")
    lines.append(f"services: [{', '.join(fm.services)}]")
    if fm.supersedes:
        lines.append(f"supersedes: [{', '.join(fm.supersedes)}]")
    if fm.superseded_by:
        lines.append(f"superseded_by: {fm.superseded_by}")
    if fm.related_to:
        lines.append(f"related_to: [{', '.join(fm.related_to)}]")
    lines.append("---")
    lines.append("")
    lines.append(f"# {fm.title}")
    lines.append("")
    lines.append(doc.body_markdown.strip())
    lines.append("")
    return "\n".join(lines)


def filename_for(doc_id: str, slug: str, prefix: str) -> str:
    if prefix == "PM":
        # PM-2024-007 -> 2024-007-slug.md
        _, year, n = doc_id.split("-")
        return f"{year}-{n}-{slug}.md"
    n = doc_id.split("-")[1]
    return f"{n}-{slug}.md"


# --- Generation orchestration --------------------------------------------------

def generate_one(
    llm,
    spec_text: str,
    doc_type: str,
    cfg: DocTypeConfig,
    requested_id: str,
    topic: Optional[str],
    existing_docs_summary: str,
) -> GeneratedDoc:
    structured_llm = llm.with_structured_output(GeneratedDoc)
    prompt = _build_user_prompt(spec_text, doc_type, cfg, requested_id, topic, existing_docs_summary)
    result: GeneratedDoc = structured_llm.invoke(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}]
    )
    if result.frontmatter.id != requested_id:
        # The LLM occasionally drifts; force the requested ID.
        result.frontmatter.id = requested_id
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--type", required=True, choices=list(DOC_TYPES))
    parser.add_argument("--count", type=int, default=1, help="Number of new docs to generate (ignored if --id is set)")
    parser.add_argument("--id", help="Generate a specific ID, e.g. ADR-007")
    parser.add_argument("--topic", help="Optional topic hint for this generation")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files at the same ID")
    parser.add_argument("--model", default=os.getenv("EAC_GENERATION_MODEL", "gpt-4o"))
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Add it to .env first.", file=sys.stderr)
        sys.exit(1)

    cfg = DOC_TYPES[args.type]
    target_dir = CORPUS_ROOT / cfg.dir_name
    target_dir.mkdir(parents=True, exist_ok=True)

    spec_text = SPEC_PATH.read_text(encoding="utf-8")
    existing = list_existing(target_dir)

    # Decide which IDs to generate
    if args.id:
        ids_to_make = [args.id]
    else:
        existing_ids = set(existing.keys())
        ids_to_make = []
        for _ in range(args.count):
            new_id = next_id(existing_ids, cfg.prefix)
            ids_to_make.append(new_id)
            existing_ids.add(new_id)

    llm = ChatOpenAI(model=args.model, temperature=0.4)
    print(f"[generate_corpus] type={args.type} model={args.model} count={len(ids_to_make)}")

    for i, doc_id in enumerate(ids_to_make, 1):
        if doc_id in existing and not args.force:
            print(f"  [{i}/{len(ids_to_make)}] {doc_id}: SKIP (already exists, use --force to overwrite)")
            continue

        print(f"  [{i}/{len(ids_to_make)}] {doc_id}: generating...", end=" ", flush=True)
        try:
            doc = generate_one(
                llm=llm,
                spec_text=spec_text,
                doc_type=args.type,
                cfg=cfg,
                requested_id=doc_id,
                topic=args.topic,
                existing_docs_summary=existing_summary(target_dir),
            )
        except Exception as e:
            print(f"FAILED: {e}")
            continue

        slug = slugify(doc.slug or doc.frontmatter.title)
        fname = filename_for(doc_id, slug, cfg.prefix)

        # If --force and the previous file had a different slug, remove the old one.
        if doc_id in existing and existing[doc_id].name != fname:
            existing[doc_id].unlink(missing_ok=True)

        out_path = target_dir / fname
        out_path.write_text(render_markdown(doc), encoding="utf-8")
        # Update existing for subsequent iterations so cross-references can pick up new docs.
        existing[doc_id] = out_path
        print(f"-> {out_path.relative_to(REPO_ROOT)}")

    print(f"[generate_corpus] done. {len(list_existing(target_dir))} doc(s) in {target_dir.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

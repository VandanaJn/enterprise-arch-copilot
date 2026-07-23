import os

import pytest
from langchain_core.documents import Document

from src.build_vector_db import (
    adr_metadata,
    attach_adr_metadata,
    build_vector_database,
    calculate_md5,
    enhance_metadata,
    get_embeddings,
    get_vector_store,
    load_documents,
    parse_frontmatter,
)

ADR_001 = """---
id: ADR-001
title: Adopt RabbitMQ for inter-service messaging
status: Accepted
date: 2021-01-15
authors: [team-alpha]
superseded_by: ADR-002
---

# Adopt RabbitMQ for inter-service messaging
"""

ADR_002 = """---
id: ADR-002
title: Adopt Kafka for event streaming
status: Accepted
supersedes: [ADR-001]
---

# Adopt Kafka for event streaming
"""


@pytest.fixture
def mock_docs_dir(tmp_path):
    """Fixture to set up mock documents in a temporary directory."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()

    # Create some mock files
    runbooks_dir = docs_dir / "runbooks"
    runbooks_dir.mkdir()
    (runbooks_dir / "test_runbook.md").write_text("This is a runbook about Kafka.")

    adrs_dir = docs_dir / "adrs"
    adrs_dir.mkdir()
    (adrs_dir / "test_adr.md").write_text("This is an ADR about architecture.")

    return str(docs_dir)


@pytest.fixture
def test_chroma_dir(tmp_path):
    """Fixture for a temporary Chroma DB directory."""
    return str(tmp_path / "chroma_db")


def test_md5_calculation():
    """Test the hashing function"""
    content = "This is a test document."
    hash1 = calculate_md5(content)
    hash2 = calculate_md5(content)
    assert hash1 == hash2
    assert hash1 == "7eb7781398042342e50bc37e93ccc854"


def test_load_documents(mock_docs_dir):
    """Test document loading from directory."""
    docs = load_documents(mock_docs_dir)
    assert len(docs) == 2
    sources = [doc.metadata["source"] for doc in docs]
    assert any("test_runbook.md" in s for s in sources)
    assert any("test_adr.md" in s for s in sources)


def test_enhance_metadata():
    """Test metadata enhancement logic."""
    docs = [
        Document(page_content="foo", metadata={"source": "path/to/runbooks/bar.md"}),
        Document(page_content="baz", metadata={"source": "path/to/adrs/qux.md"}),
        Document(page_content="quux", metadata={"source": "other/path.md"}),
    ]
    enhanced = enhance_metadata(docs)
    assert enhanced[0].metadata["document_type"] == "runbook"
    assert enhanced[1].metadata["document_type"] == "adr"
    assert enhanced[2].metadata["document_type"] == "unknown"


# --- ADR frontmatter parsing --------------------------------------------------


def test_parse_frontmatter_reads_leading_yaml_block():
    fm = parse_frontmatter(ADR_001)
    assert fm["id"] == "ADR-001"
    assert fm["superseded_by"] == "ADR-002"
    assert fm["title"] == "Adopt RabbitMQ for inter-service messaging"


def test_parse_frontmatter_returns_empty_without_a_block():
    assert parse_frontmatter("# Just a heading\n\nSome body text.") == {}


def test_parse_frontmatter_ignores_a_block_that_is_not_at_the_top():
    assert parse_frontmatter("Intro line\n\n---\nid: ADR-001\n---\n") == {}


def test_adr_metadata_extracts_supersession_fields():
    assert adr_metadata(ADR_001) == {"adr_id": "ADR-001", "superseded_by": "ADR-002"}


def test_adr_metadata_flattens_list_valued_supersedes():
    assert adr_metadata(ADR_002) == {"adr_id": "ADR-002", "supersedes": "ADR-001"}


def test_adr_metadata_joins_multiple_superseded_ids():
    content = "---\nid: ADR-009\nsupersedes: [ADR-003, ADR-004]\n---\n\n# Body\n"
    assert adr_metadata(content)["supersedes"] == "ADR-003,ADR-004"


def test_adr_metadata_omits_absent_fields():
    content = "---\nid: ADR-005\nstatus: Accepted\n---\n\n# Body\n"
    assert adr_metadata(content) == {"adr_id": "ADR-005"}


def test_adr_metadata_ignores_non_adr_documents():
    """Runbooks carry RB-NNN ids; only ADR ids become adr_id."""
    content = "---\nid: RB-004\ntitle: Kafka consumer lag spike\n---\n\n# Body\n"
    assert adr_metadata(content) == {}


def test_attach_adr_metadata_tags_documents_in_place():
    docs = [
        Document(page_content=ADR_001, metadata={"source": "docs/adrs/001-rabbitmq.md"}),
        Document(page_content=ADR_002, metadata={"source": "docs/adrs/002-kafka.md"}),
        Document(page_content="No frontmatter here.", metadata={"source": "docs/runbooks/x.md"}),
    ]
    tagged = attach_adr_metadata(docs)

    assert tagged[0].metadata["adr_id"] == "ADR-001"
    assert tagged[0].metadata["superseded_by"] == "ADR-002"
    assert "supersedes" not in tagged[0].metadata
    assert tagged[1].metadata["supersedes"] == "ADR-001"
    assert tagged[2].metadata == {"source": "docs/runbooks/x.md"}


def test_attach_adr_metadata_values_are_chroma_safe_scalars():
    """Chroma rejects list/None metadata values, so everything must be a str."""
    docs = [Document(page_content=ADR_002, metadata={"source": "docs/adrs/002-kafka.md"})]
    metadata = attach_adr_metadata(docs)[0].metadata
    assert all(isinstance(v, str) for v in metadata.values())


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here",
    reason="Requires OpenAI API Key",
)
def test_build_vector_database_integration(mock_docs_dir, test_chroma_dir):
    """Test the full build process using temporary directories."""

    # Build DB
    build_vector_database(docs_dir=mock_docs_dir, chroma_db_dir=test_chroma_dir)

    # Assert DB exists
    assert os.path.exists(test_chroma_dir)

    # Validate contents
    embeddings = get_embeddings()
    vector_store = get_vector_store(test_chroma_dir, embeddings)

    count = vector_store._collection.count()
    assert count > 0

    # Verify metadata injection worked
    results = vector_store.similarity_search("kafka", k=1)
    assert len(results) > 0
    assert "document_type" in results[0].metadata
    assert "document_hash" in results[0].metadata

    # Explicitly delete to release locks
    del vector_store


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here",
    reason="Requires OpenAI API Key",
)
def test_build_indexes_supersession_metadata(tmp_path):
    """Supersession fields survive chunking and land on every chunk of the ADR."""
    docs_dir = tmp_path / "docs" / "adrs"
    docs_dir.mkdir(parents=True)
    (docs_dir / "001-rabbitmq.md").write_text(ADR_001, encoding="utf-8")
    (docs_dir / "002-kafka.md").write_text(ADR_002, encoding="utf-8")
    chroma_dir = str(tmp_path / "chroma_db")

    build_vector_database(docs_dir=str(tmp_path / "docs"), chroma_db_dir=chroma_dir)

    vector_store = get_vector_store(chroma_dir, get_embeddings())
    stored = vector_store.get(where={"adr_id": "ADR-001"})
    assert stored["ids"], "no chunk indexed under adr_id=ADR-001"
    assert all(m["superseded_by"] == "ADR-002" for m in stored["metadatas"])
    del vector_store


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here",
    reason="Requires OpenAI API Key",
)
def test_avoids_duplicates_on_rerun(mock_docs_dir, test_chroma_dir):
    """Test the UPSERT logic by running the builder twice."""

    # First build
    build_vector_database(docs_dir=mock_docs_dir, chroma_db_dir=test_chroma_dir)
    embeddings = get_embeddings()
    vector_store = get_vector_store(test_chroma_dir, embeddings)
    initial_count = vector_store._collection.count()
    del vector_store  # Release lock

    # Second build (should skip unchanged files)
    build_vector_database(docs_dir=mock_docs_dir, chroma_db_dir=test_chroma_dir)

    vector_store_second = get_vector_store(test_chroma_dir, embeddings)
    final_count = vector_store_second._collection.count()
    del vector_store_second  # Release lock

    assert initial_count == final_count

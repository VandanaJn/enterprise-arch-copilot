import os

import pytest
from langchain_core.documents import Document

from src.build_vector_db import (
    build_vector_database,
    calculate_md5,
    enhance_metadata,
    get_embeddings,
    get_vector_store,
    load_documents,
)


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

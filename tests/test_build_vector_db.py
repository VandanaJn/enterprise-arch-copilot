import os
import shutil
import pytest
from src.build_vector_db import build_vector_database, calculate_md5, CHROMA_DB_DIR
from src.generate_mock_data import generate_unstructured_data, create_directories, DOCS_DIR
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from dotenv import load_dotenv
import tempfile

load_dotenv()

TEST_CHROMA_DIR = tempfile.mkdtemp()

@pytest.fixture(autouse=True)
def setup_and_teardown(monkeypatch):
    """Ensure a clean environment before and after testing Vector DB buildup."""
    # Monkeypatch the CHROMA_DB_DIR variable in build_vector_db so it uses our temp dir
    import src.build_vector_db as build_vector_db
    monkeypatch.setattr(build_vector_db, "CHROMA_DB_DIR", TEST_CHROMA_DIR)
    
    # Setup test docs
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)

    create_directories()
    generate_unstructured_data()
    
    yield
    
    # Teardown docs
    if os.path.exists(DOCS_DIR):
        shutil.rmtree(DOCS_DIR)
        
    # We do NOT delete the chroma db dir here synchronously to avoid Windows file lock errors
    # (The OS will clean up the temp directory eventually, or we can just leave it)

def test_md5_calculation():
    """Test the hashing function"""
    content = "This is a test document."
    hash1 = calculate_md5(content)
    hash2 = calculate_md5(content)
    assert hash1 == hash2
    assert hash1 == "7eb7781398042342e50bc37e93ccc854"

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here", reason="Requires OpenAI API Key")
def test_build_vector_database_inserts_data():
    """Test that the script successfully chunks and embeds documents into Chroma."""
    
    # Build DB
    build_vector_database()
    
    # Assert DB exists
    assert os.path.exists(CHROMA_DB_DIR)
    
    # Validate contents
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    
    count = vector_store._collection.count()
    assert count > 0
    
    # Verify metadata injection worked
    results = vector_store.similarity_search("kafka", k=1)
    assert len(results) > 0
    assert "document_type" in results[0].metadata
    assert "document_hash" in results[0].metadata

@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here", reason="Requires OpenAI API Key")
def test_build_vector_database_avoids_duplicates_on_rerun():
    """Test the UPSERT logic by running the builder twice and ensuring chunk counts don't double."""
    
    # First build
    build_vector_database()
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    initial_count = vector_store._collection.count()
    
    # Second build (should skip unchanged files based on MD5)
    build_vector_database()
    
    vector_store_second = Chroma(persist_directory=CHROMA_DB_DIR, embedding_function=embeddings)
    final_count = vector_store_second._collection.count()
    
    assert initial_count == final_count

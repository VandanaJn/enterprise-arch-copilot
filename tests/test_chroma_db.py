"""Smoke test that the built ChromaDB is queryable.

Runs against the isolated tests/test_data/chroma_db/ populated by the
session-scoped `built_test_data` fixture in conftest.py.
"""

import pytest
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from src import config


@pytest.mark.integration
def test_chroma_is_queryable(built_test_data):
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(persist_directory=config.chroma_dir(), embedding_function=embeddings)
    try:
        count = vector_store._collection.count()
        assert count > 0, "Built Chroma DB is empty"

        results = vector_store.similarity_search("504 gateway timeout", k=2)
        assert len(results) > 0, "Similarity search returned no documents"
        assert any("checkout" in r.page_content.lower() or "504" in r.page_content for r in results)
    finally:
        del vector_store

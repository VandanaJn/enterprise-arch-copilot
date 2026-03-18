import os
import pytest
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

from src.build_vector_db import CHROMA_DB_DIR


@pytest.mark.integration
def test_database():
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"❌ Error: Database directory '{CHROMA_DB_DIR}' not found.")
        print("Did you remember to run 'python build_vector_db.py'?")
        return
        
    embeddings = OpenAIEmbeddings()
    
    # Load the vector store from the local directory
    vector_store = Chroma(
        persist_directory=CHROMA_DB_DIR, 
        embedding_function=embeddings
    )
    
    # The LangChain Chroma wrapper exposes the underlying chromadb collection, 
    # which we can use to count the exact number of chunks stored.
    count = vector_store._collection.count()
    print(f"✅ Successfully connected to ChromaDB!")
    print(f"📊 Total document chunks stored: {count}")
    
    if count > 0:
        print("\n🔍 Running a test query: '504 gateway timeout'")
        
        # Perform a basic similarity search, asking for the top 2 closest matches
        results = vector_store.similarity_search("504 gateway timeout", k=2)
        
        for i, doc in enumerate(results):
            print(f"\n--- Top Result {i+1} ---")
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print(f"Document Type Tag: {doc.metadata.get('document_type', 'Unknown')}")
            print(f"Content snippet: {doc.page_content[:150]}...")
            
    # Explicitly clear the object to help release file locks on Windows
    del vector_store
            
if __name__ == "__main__":
    test_database()

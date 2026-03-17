import os
import hashlib
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

# Get the absolute root directory of the project (one level up from src/)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCS_DIR = os.path.join(ROOT_DIR, "docs")
CHROMA_DB_DIR = os.path.join(ROOT_DIR, "chroma_db")

def calculate_md5(content: str) -> str:
    """Generate an MD5 hash of the string content."""
    return hashlib.md5(content.encode('utf-8')).hexdigest()

def build_vector_database():
    """Loads markdown files, chunks them semantically, and stores them in Chroma.
       Implements hash-based UPSERT to avoid duplicates.
    """
    
    # 1. Ensure API Key is set
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        print("ERROR: Please update the .env file with your actual OPENAI_API_KEY.")
        return

    print("Loading documents from directory...")
    # 2. Check if docs directory exists
    if not os.path.exists(DOCS_DIR):
        print(f"❌ Error: Source directory '{DOCS_DIR}' not found.")
        print("Please run 'python src/generate_mock_data.py' first to generate the mock documents.")
        return

    # 3. Load the unstructured Markdown documents
    # By using the glob pattern '**/*.md', we grab both ADRs and Runbooks recursively.
    loader = DirectoryLoader(
        DOCS_DIR, 
        glob="**/*.md", 
        loader_cls=TextLoader,
        loader_kwargs={'autodetect_encoding': True} 
    )
    documents = loader.load()
    print(f"Loaded {len(documents)} document(s).")

    # 3. Initialize Embedding Model & ChromaDB connection
    embeddings = OpenAIEmbeddings()
    vector_store = Chroma(
        persist_directory=CHROMA_DB_DIR, 
        embedding_function=embeddings
    )

    # 4. Hash Checking and Deduplication Filter
    print("Checking document hashes for updates...")
    docs_to_process = []
    
    for doc in documents:
        # Calculate the hash of the raw document content
        doc_hash = calculate_md5(doc.page_content)
        # Store the hash in metadata so it persists to the chunks later
        doc.metadata["document_hash"] = doc_hash
        source_path = doc.metadata.get("source", "")
        
        # Query Chroma to see if chunks from this exact file already exist
        existing_chunks = vector_store.get(where={"source": source_path})
        
        if existing_chunks and len(existing_chunks.get('ids', [])) > 0:
            # Check the hash of the first existing chunk for this document
            first_existing_hash = existing_chunks['metadatas'][0].get("document_hash")
            
            if first_existing_hash == doc_hash:
                print(f"  [SKIPPED] Unmodified: {source_path}")
                continue
            else:
                print(f"  [UPDATED] Changes detected. Deleting old chunks for: {source_path}")
                vector_store.delete(ids=existing_chunks['ids'])
        else:
            print(f"  [NEW] Found new document: {source_path}")
            
        # If it's new or updated, queue it for semantic chunking
        docs_to_process.append(doc)

    if not docs_to_process:
        print("✅ No changed documents found. Vector database is up to date!")
        return

    # 5. Semantic Chunking for NEW or UPDATED documents only
    print(f"Splitting {len(docs_to_process)} document(s) into semantic chunks...")
    
    semantic_splitter = SemanticChunker(embeddings)
    semantic_chunks = semantic_splitter.split_documents(docs_to_process)
    print(f"Initial split yielded {len(semantic_chunks)} semantic chunk(s).")

    max_size_fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        length_function=len
    )
    final_chunks = max_size_fallback_splitter.split_documents(semantic_chunks)
    print(f"After enforcing max size limit, we have {len(final_chunks)} final chunk(s).")

    # 6. Enhance Metadata for Hybrid Filtering
    print("Injecting explicit metadata tags...")
    for chunk in final_chunks:
        source_path = chunk.metadata.get("source", "").lower()
        if "runbooks" in source_path:
            chunk.metadata["document_type"] = "runbook"
        elif "adrs" in source_path:
            chunk.metadata["document_type"] = "adr"
        else:
            chunk.metadata["document_type"] = "unknown"

    # 7. Add only the new/updated chunks into Chroma DB
    print(f"Inserting {len(final_chunks)} new chunks into Chroma DB...")
    vector_store.add_documents(documents=final_chunks)
    
    print(f"✅ Successfully updated localized Vector Database at: ./{CHROMA_DB_DIR}/")
    
    # Explicitly clear the object to help release file locks on Windows
    del vector_store

if __name__ == "__main__":
    build_vector_database()

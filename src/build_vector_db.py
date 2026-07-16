import hashlib
import os

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src import config

# Load environment variables (OPENAI_API_KEY)
load_dotenv()


def calculate_md5(content: str) -> str:
    """Generate an MD5 hash of the string content."""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def get_embeddings():
    """Returns the OpenAIEmbeddings instance."""
    return OpenAIEmbeddings()


def get_vector_store(persist_directory: str, embeddings):
    """Returns the Chroma instance."""
    return Chroma(persist_directory=persist_directory, embedding_function=embeddings)


def load_documents(directory: str):
    """Loads markdown documents from the specified directory."""
    if not os.path.exists(directory):
        print(f"[ERROR] Source directory '{directory}' not found.")
        return []

    loader = DirectoryLoader(
        directory,
        glob="**/*.md",
        loader_cls=TextLoader,
        loader_kwargs={"autodetect_encoding": True},
    )
    return loader.load()


def filter_changed_documents(documents, vector_store):
    """Compares hashes and returns only new or updated documents."""
    docs_to_process = []
    print("Checking document hashes for updates...")

    for doc in documents:
        doc_hash = calculate_md5(doc.page_content)
        doc.metadata["document_hash"] = doc_hash
        source_path = doc.metadata.get("source", "")

        existing_chunks = vector_store.get(where={"source": source_path})

        if existing_chunks and len(existing_chunks.get("ids", [])) > 0:
            first_existing_hash = existing_chunks["metadatas"][0].get("document_hash")

            if first_existing_hash == doc_hash:
                print(f"  [SKIPPED] Unmodified: {source_path}")
                continue
            else:
                print(f"  [UPDATED] Changes detected. Deleting old chunks for: {source_path}")
                vector_store.delete(ids=existing_chunks["ids"])
        else:
            print(f"  [NEW] Found new document: {source_path}")

        docs_to_process.append(doc)
    return docs_to_process


def chunk_documents(documents, embeddings):
    """Handles semantic and character-based splitting of documents."""
    print(f"Splitting {len(documents)} document(s) into semantic chunks...")

    semantic_splitter = SemanticChunker(embeddings)
    semantic_chunks = semantic_splitter.split_documents(documents)
    print(f"Initial split yielded {len(semantic_chunks)} semantic chunk(s).")

    max_size_fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=200, length_function=len
    )
    final_chunks = max_size_fallback_splitter.split_documents(semantic_chunks)
    print(f"After enforcing max size limit, we have {len(final_chunks)} final chunk(s).")
    return final_chunks


def enhance_metadata(chunks):
    """Adds metadata tags (e.g., document_type) based on document source path."""
    print("Injecting explicit metadata tags...")
    for chunk in chunks:
        source_path = chunk.metadata.get("source", "").lower()
        if "runbooks" in source_path:
            chunk.metadata["document_type"] = "runbook"
        elif "adrs" in source_path:
            chunk.metadata["document_type"] = "adr"
        elif "postmortems" in source_path:
            chunk.metadata["document_type"] = "postmortem"
        elif "design_docs" in source_path:
            chunk.metadata["document_type"] = "design_doc"
        else:
            chunk.metadata["document_type"] = "unknown"
    return chunks


def build_vector_database(docs_dir=None, chroma_db_dir=None):
    """Build or update the vector database from markdown docs.

    Raises:
        RuntimeError: if OPENAI_API_KEY is missing or no documents are found.
            (Silent return here masks setup errors in scripts and CI.)
    """
    if docs_dir is None:
        docs_dir = config.docs_dir()
    if chroma_db_dir is None:
        chroma_db_dir = config.chroma_dir()

    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        raise RuntimeError("OPENAI_API_KEY is not set. Update .env before building the vector DB.")

    documents = load_documents(docs_dir)
    if not documents:
        raise RuntimeError(
            f"No markdown documents found under '{docs_dir}'. "
            "Run `python -m src.generate_mock_data` first to populate it."
        )
    print(f"Loaded {len(documents)} document(s).")

    # 2. Get embeddings and vector store
    embeddings = get_embeddings()
    vector_store = get_vector_store(chroma_db_dir, embeddings)

    # 3. Filter for changed documents
    docs_to_process = filter_changed_documents(documents, vector_store)

    if not docs_to_process:
        print("[OK] No changed documents found. Vector database is up to date!")
        return

    # 4. Chunk changed documents
    final_chunks = chunk_documents(docs_to_process, embeddings)

    # 5. Enhance metadata
    final_chunks = enhance_metadata(final_chunks)

    # 6. Upsert into vector store
    print(f"Inserting {len(final_chunks)} new chunks into Chroma DB...")
    vector_store.add_documents(documents=final_chunks)

    print(f"[OK] Successfully updated localized Vector Database at: ./{chroma_db_dir}/")

    # Release file locks
    del vector_store


if __name__ == "__main__":
    build_vector_database()

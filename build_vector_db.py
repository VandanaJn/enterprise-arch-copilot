import os
from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

# Load environment variables (OPENAI_API_KEY)
load_dotenv()

DOCS_DIR = "docs"
CHROMA_DB_DIR = "chroma_db"

def build_vector_database():
    """Loads markdown files, chunks them semantically, and stores them in Chroma."""
    
    # 1. Ensure API Key is set
    if not os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") == "your_openai_api_key_here":
        print("ERROR: Please update the .env file with your actual OPENAI_API_KEY.")
        return

    print("Loading documents from directory...")
    # 2. Load the unstructured Markdown documents
    # By using the glob pattern '**/*.md', we grab both ADRs and Runbooks recursively.
    loader = DirectoryLoader(
        DOCS_DIR, 
        glob="**/*.md", 
        loader_cls=TextLoader,
        loader_kwargs={'autodetect_encoding': True} 
    )
    documents = loader.load()
    print(f"Loaded {len(documents)} document(s).")

    # 3. Step 2.1: True Semantic Chunking (Transformation)
    # SemanticChunker uses the embedding model to find structural breaks in meaning,
    # rather than just splitting on arbitrary character counts or newlines.
    print("Splitting documents into semantic chunks...")
    
    # Initialize the embedding model (defaults to text-embedding-ada-002)
    embeddings = OpenAIEmbeddings()
    
    semantic_splitter = SemanticChunker(embeddings)
    
    # First, split documents semantically
    semantic_chunks = semantic_splitter.split_documents(documents)
    print(f"Initial split yielded {len(semantic_chunks)} semantic chunk(s).")

    # Step 2.2: Hard Limit Fallback
    # Even semantic chunks must have a maximum length to fit in LLM context windows
    # and to ensure vector embeddings don't become too "diluted". 
    # We use a structural splitter to enforce a hard maximum length of 2000 characters.
    max_size_fallback_splitter = RecursiveCharacterTextSplitter(
        chunk_size=2000,
        chunk_overlap=200,
        length_function=len
    )
    
    final_chunks = max_size_fallback_splitter.split_documents(semantic_chunks)
    print(f"After enforcing max size limit, we have {len(final_chunks)} final chunk(s).")

    # 4. Load into Chroma Vector Database
    print("Building Chroma DB...")
    
    # Create the vector store. This will parse the chunks, send them to OpenAI to get vectorized,
    # and save the resulting vectors locally in the CHROMA_DB_DIR.
    vector_store = Chroma.from_documents(
        documents=final_chunks, 
        embedding=embeddings, 
        persist_directory=CHROMA_DB_DIR
    )
    
    print(f"Successfully created localized Vector Database at: ./{CHROMA_DB_DIR}/")

if __name__ == "__main__":
    build_vector_database()

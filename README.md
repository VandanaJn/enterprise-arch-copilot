# Enterprise Architecture Copilot

This project is an advanced Retrieval-Augmented Generation (RAG) system built with LangChain, LangGraph, and OpenAI embeddings. It simulates an AI engineering assistant capable of querying internal enterprise documentation (ADRs, runbooks) and structured metadata (service catalog, API endpoints) via SQLite and ChromaDB.

## Project Features

* **Data Generation**: Procedurally creates rich mock Architectural Decision Records (ADRs), runbooks, and a relational service catalog.
* **Semantic Chunking**: Employs LangChain's `SemanticChunker` to semantically divide raw markdown documentation.
* **Hybrid Search Ready**: Injects unstructured documents with explicit metadata (e.g. `document_type: adr`) for targeted exact-match filtering alongside semantic similarity.
* **Idempotent Vector Insertion**: Implements a custom UPSERT strategy utilizing MD5 document hashing to guarantee the vector database is only populated with updated or new chunks, preventing hallucinations caused by duplications on rerun.

## Project Structure
- `src/`: Core Python application logic and agents.
  - `generate_mock_data.py`: Generates the raw `.md` documents and the SQLite databases.
  - `build_vector_db.py`: Read documents, chunks them semantically, constructs embeddings, and stores them in a local Chroma vector database.
- `tests/`: Comprehensive Pytest unit tests for logical guarantees.
- `conftest.py`: Root-level path configuration so `tests/` can easily import `src/` modules.
- `DECISIONS.md`: A live architectural decisions log explaining the "why" behind framework choices.

*Note: Automatically generated database folders (`docs/`, `chroma_db/`, `engineering_data.db`) are ignored by git.*

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/VandanaJn/enterprise-arch-copilot.git
   cd enterprise-arch-copilot
   ```

2. **Set up a Python virtual environment:**
   ```bash
   python -m venv venv
   
   # Windows
   .\venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set your API Keys:**
   Create a `.env` file in the root directory and append your OpenAI API key for generating embeddings:
   ```env
   OPENAI_API_KEY=your_actual_api_key_here
   ```

## Usage

**Step 1: Generate Mock Data**
```bash
python src/generate_mock_data.py
```
This generates a `docs/` folder containing dummy ADRs and Runbooks, and initializes an `engineering_data.db` SQLite database.

**Step 2: Build the Vector Database**
```bash
python src/build_vector_db.py
```
This script processes the markdown files, calculates their hashes, transforms them recursively into chunks, and stores their embeddings in a local `chroma_db/` directory. 

## Running Tests

**Quick run (no API key or built DB required)** — runs unit tests only (e.g. data generation, chunking, metadata):
```bash
pytest tests/ -v -m "not integration"
```

**Full test suite** — integration tests need `OPENAI_API_KEY` and a built vector DB. One-time setup:
1. Set `OPENAI_API_KEY` in your `.env` file.
2. Generate mock data and build the vector DB:
   ```bash
   python src/generate_mock_data.py
   python src/build_vector_db.py
   ```
3. Run all tests:
   ```bash
   pytest tests/ -v
   ```

Integration tests (agent routing, vector search, Chroma connectivity) are marked with `@pytest.mark.integration` and are skipped when the API key is missing or when `chroma_db/` does not exist.
# Architecture & Technology Decisions Log

This document tracks the rationale behind key technical choices for the Enterprise Architecture Copilot.

## 1. Project Initialization & Dependencies

### Python Virtual Environment (`venv`)
*   **Decision:** Use standard Python `venv` with a `requirements.txt`.
*   **Rationale:** Keeps dependencies isolated and makes the project easily reproducible.

### LangChain Ecosystem (`langchain`, `langgraph`, `langsmith`)
*   **Decision:** Build the agentic routing logic using LangChain v0.3.x and LangGraph.
*   **Rationale:** LangChain provides the standard abstractions for vector stores and LLM interactions. LangGraph is newly preferred (v1.0 best practices) over legacy `AgentExecutor` for building reliable, cyclical agent decision trees (the "Router" aspect of this project).

### Structured Database (`sqlite3` / `SQLAlchemy`)
*   **Decision:** Use SQLite for the structured data store, managed via the standard `sqlite3` library (with `SQLAlchemy` loaded for future ORM needs if complexity grows).
*   **Rationale:** Zero-configuration. Perfect for a local demonstration of structured metadata querying without the overhead of spinning up a Postgres container.

### Unstructured Database (`chromadb`)
*   **Decision:** Use ChromaDB for the local vector store.
*   **Rationale:** Runs entirely local/in-memory, integrates seamlessly with LangChain, and avoids the need for a cloud vector database subscription during development and interviews.

### LLM Provider (`langchain-openai`)
*   **Decision:** Use OpenAI (GPT-4o or `gpt-4o-mini`).
*   **Rationale:** 
    *   Provides the most reliable function-calling/tool-calling capabilities required for an agentic router to decide between SQL and Vector tools.
    *   Excellent native support for `response_format={ "type": "json_object" }` and structured output parsing, which guarantees the agent returns data arrays and thought processes in a machine-readable format that LangGraph can easily route.

## 2. Unstructured Data Ingestion (Vector Search)

### True Semantic Chunking (`SemanticChunker`)
*   **Decision:** We are using LangChain's `SemanticChunker` (from `langchain-experimental`).
*   **Rationale:** `RecursiveCharacterTextSplitter` is *structural* chunking, not *semantic* chunking. 
    *   **True Semantic Chunking** embeds every sentence and calculates the cosine distance between them. It groups sentences together into a chunk until the semantic meaning drastically shifts (a "breakpoint"), at which point it starts a new chunk.
    *   **Chunk Size:** Unlike structural splitter, there is **no fixed chunk size** (like 1000 characters). The chunk size is completely variable and is determined dynamically by the meaning of the text. If an architectural explanation is 3 sentences, the chunk is 3 sentences. If the explanation takes 15 sentences before moving to a new topic, the chunk is 15 sentences. You control the length indirectly by adjusting the breakpoint threshold (e.g., `breakpoint_threshold_type="percentile"`).
    *   **Fallback Limit:** We still combine this with a structural splitter as a fallback to enforce a hard maximum limit (e.g., 2000 characters) to protect LLM context windows in cases where a topic never shifts.
    *   **Why this matters:** Unlike arbitrary character limits which might split related thoughts, the `SemanticChunker` guarantees that all text within a chunk is contextually related. This significantly improves retrieval accuracy in RAG systems.

### Embedding Model (`OpenAIEmbeddings`)
*   **Decision:** We are using LangChain's default OpenAI embedding configuration, which resolves to high-dimensionality models (like `text-embedding-ada-002` or `text-embedding-3-small`).
*   **Rationale & Dimensionality Trade-offs:**
    *   **High Dimensionality (1536 dimensions):** OpenAI models generate 1536-dimensional vectors. This massive semantic space allows the model to capture highly complex, nuanced engineering concepts (e.g., the architectural differences between Kafka vs. RabbitMQ). 
    *   **Compared to Low Dimensionality (e.g., 384 dimensions):** Smaller, local open-source models (like `all-MiniLM-L6-v2`) are much faster and cheaper to run, but they often collapse complex comparative topics into generic buckets (e.g., just "messaging systems"), reducing RAG accuracy for Staff-level architecture queries.
    *   **The Trade-off (Cost vs. Accuracy):** 1536-dimensional vectors take 4x the RAM and storage in a vector database compared to 384-dimensional vectors, and computing cosine distance at query time is mathematically heavier. For enterprise scale (millions of docs), this strictly increases cloud vector DB hosting costs.
    *   **Why Hosted OpenAI over Local Open-Source (e.g., BAAI/bge-large)?** While models like `bge-large` (1024 dimensions) often beat OpenAI on retrieval benchmarks and offer data privacy, hosting them locally requires PyTorch dependency management and hardware acceleration (GPUs). A reliable, hosted API eliminates that infrastructure complexity for this use case.
    *   *(Note: Newer models like OpenAI's `text-embedding-3` support "Matryoshka embeddings", allowing developers to truncate the 1536 dimensions down to 512 dimensions while retaining almost all accuracy, effectively solving the storage cost trade-off).*

### Deduplication via MD5 Hashing (UPSERT)
*   **Decision:** We calculate an MD5 hash of the raw document content, store it in chunk metadata, and compare hashes against the existing ChromaDB prior to running semantic splits or inserting embeddings.
*   **Rationale:** Standard vector databases do not natively prevent data duplication if the same scripts are run multiple times. If an ADR gets updated, doing a naively-appended embedding run will result in Chroma returning both the "old" meaning and the "new" meaning simultaneously to the LLM, causing hallucinations. By injecting document-level hashes, we implemented a custom true `UPSERT`. We skip unchanged files, and automatically delete old chunks for updated files before re-embedding them.
### Manual Metadata Injection for Hybrid Filtering
*   **Decision:** We are manually injecting a `document_type` metadata field (e.g., `adr` or `runbook`) into each parsed chunk based on its source folder.
*   **Rationale:** While vector search (Semantic Similarity) is excellent at retrieving contextually similar text, it is poor at exact-match filtering. By explicitly tagging the chunks in ChromaDB with structured metadata, we unlock **Hybrid Search**. This allows the Agent Router to later issue a targeted query like: *"Find me documents semantically similar to '504 timeout', but apply a hard filter where `metadata.document_type == 'runbook'`"* This vastly reduces LLM hallucination on large enterprise repositories.

## 3. Agent Architecture

### Single-Agent Router vs. Multi-Agent Systems
*   **Decision:** Use a single-agent router architecture instead of a multi-agent "supervisor" pattern.
*   **Rationale:** 
    *   **Efficiency:** A single-agent router is more token-efficient and reduces latency by avoiding inter-agent communication overhead.
    *   **Iterative Reasoning:** The current router can already perform sequential tool calls (e.g., query SQL then Search Vector DB) within a single execution loop.
    *   **Complexity Management:** Multi-agent systems add significant orchestration complexity (managing handoffs, state merging, and specialized prompts). For the current scope of RAG and SQL retrieval, a single well-prompted agent is more robust and easier to maintain.
    *   **Future Proofing:** This single-agent approach is sufficient for the current simple use case. If the system grows to include significantly more tools or highly specialized domain logic, the architecture can be refactored into a multi-agent supervisor/worker pattern later.

### Retries and Backoff (OpenAI / Chroma)
*   **Decision:** No retries or circuit breaker in the current demo; failures surface immediately to the user.
*   **Rationale:** Keeps the codebase simple for portfolio and local use. For production we would add: (1) **Retries with backoff** (e.g. `tenacity` or LangChain’s built-in retry) on transient OpenAI/network errors, with exponential backoff and a max attempt count; (2) **Circuit breaker** (e.g. `pybreaker` or a small state machine) around external calls so repeated failures stop hammering the API and allow partial degradation (e.g. SQL-only mode if Chroma is down). We would also consider timeouts and idempotency for write paths (e.g. vector upserts).

### Observability (LangSmith)
*   **Decision:** Use LangSmith for tracing when configured via environment variables (`LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`). No application code changes are required; LangChain/LangGraph auto-instrument when these are set.
*   **Rationale:** LangSmith is the standard observability layer for the LangChain ecosystem. With `.env` (or `.env.example` copied to `.env`) populated, every agent run, tool call, and LLM request is traced to the configured project. This supports debugging, latency analysis, and token usage visibility without adding custom logging or metrics code. The template `.env.example` documents the optional variables; tracing is off if `LANGSMITH_API_KEY` is unset.

# Build retrieval-augmented generation (RAG) pipelines combining vector search and structured data sources to enable contextual search across engineering documentation 

# Use c:\learning\lca-langgraph-essentials and c:\learning\lca-lc-foundations and c:\learning\intro-to-langsmith for langchain/langgraph/langsmith exapmles examples, we want to follow version1.0 best practices.

Steps:
# Steps: Create data models for unstructured and structured data sources. 
# Steps: Create vector database for unstructured data sources. 
# Steps: Create SQL database for structured data sources. 
# Steps: Create LangChain/LangGraph/LangSmith pipeline for unstructured data sources. 
# Steps: Create LangChain/LangGraph/LangSmith pipeline for structured data sources. 
# Steps: Create LangChain/LangGraph/LangSmith pipeline for hybrid data sources. 

At Every step first plan the steps and then execute them after confirmation.
Validate the output and test every step before moving to the next step.
Write small code, so that code review is easy and test it before moving to the next step.
Create sample data and script to generate structured and unstructured data.

## Data Sources (The "Engineering Documentation")

To keep it simple, we simulate a company's internal documentation:

### 1. Unstructured Data (Vector Search)
*   **Architecture Decision Records (ADRs) & RFCs:** Markdown files detailing *why* certain architectural choices were made (e.g., "Why we chose Kafka over RabbitMQ").
*   **Operational Runbooks:** Markdown files detailing *how* to fix specific incidents (e.g., "How to restart the payment processing service").
*   *Implementation:* Chunked and embedded into a local Vector DB (like ChromaDB or FAISS).

### 2. Structured Data Sources (SQL Search)
*   **Service Catalog (Microservices Registry):** A structured SQL table listing every microservice, its owner team, its current version, and its PagerDuty on-call rotation.
*   **API Endpoints:** A structured table mapping API routes to the microservice that handles them.
*   *Implementation:* A simple local SQLite database containing a few mocked tables.

## The Agentic Pipeline (How it works)

You will use LangChain (or LlamaIndex) to build a **Router Agent**. The agent receives a query and decides which tool to use.

1.  **Scenario 1: Pure Unstructured Vector Search**
    *   *User Query:* "What was the rationale behind migrating our payment gateway to the new AWS architecture?"
    *   *Agent Action:* The LLM detects this is a conceptual question. It routes the query to the **Vector Database Tool**, retrieves the relevant ADR markdown file, and summarizes the "why".

2.  **Scenario 2: Pure Structured SQL Search**
    *   *User Query:* "Who is the owner of the `user-profile-service` and what is the current deployed version?"
    *   *Agent Action:* The LLM detects this is a factual metadata question. It routes the query to the **SQL Database Tool**, generates a `SELECT` statement against the SQLite Service Catalog, and returns the team name and version.

3.  **Scenario 3: The Hybrid "Contextual Search" (The Staff Level Flex)**
    *   *User Query:* "The `/api/v1/checkout` endpoint is failing with a 504 timeout. Who do I contact, and what is the runbook to mitigate this?"
    *   *Agent Action 1 (Structured):* The LLM queries the SQL Database to find out which microservice owns `/api/v1/checkout` (Result: `checkout-service`) and who owns it (Result: `Team Alpha`).
    *   *Agent Action 2 (Unstructured):* The LLM takes `checkout-service` and queries the Vector Database for runbooks specifically related to that service.
    *   *Result:* A consolidated response: "Contact Team Alpha. Here are the steps from their runbook to mitigate a 504 on the checkout service..."

## Why this is perfect for you:
1.  **It completely validates your resume:** When an interviewer asks, "Tell me about this RAG pipeline you built combining vector and structured data," you can describe this *exact* architecture.
2.  **It is highly relevant:** This is exactly the type of platform tooling companies like FINRA and AppFolio are trying to build internally.
3.  **It is bounded and buildable:** You can build this in Python in a few days using basic LangChain, SQLite, and Chroma. No massive cloud infrastructure required.

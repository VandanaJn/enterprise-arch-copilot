# The Staff SE Interview Architecture Copilot

**Target Audience:** You (for interview preparation)
**Focus:** System Design, API architecture, distributed systems patterns, and coding interview prep.

## Overview
A hands-on, lightweight agentic RAG system that acts as your personal interviewer and technical study buddy. It uses your structured resume/experience data alongside unstructured engineering architectures and interview questions. 

You can use this project to actually study for your interviews while simultaneously demonstrating a highly relevant, applied AI architecture project to your interviewers.

## Data Sources

### 1. Structured Data (SQL/JSON/CSV)
*   **Your Experience Timeline (JSON/SQL):** A structured database of your past projects, the tools used (e.g., Python, AWS, Kafka), the scale (e.g., 10k RPS), and the outcomes.
*   **Job Descriptions (CSV/JSON):** The specific requirements, tech stack, and responsibilities parsed from the JDs you are applying to (like the ones from AppFolio, FINRA, Ridgeline).

### 2. Unstructured Data (Markdown/PDFs)
*   **System Design Case Studies (Markdown/PDF):** High-level architectural teardowns of big systems (e.g., "How Uber scales their dispatch system", "Netflix microservices").
*   **Engineering Blogs & Best Practices (Markdown):** Articles on event-driven architecture, API Gateway patterns, etc.

## How the Agentic System Works (The "Hands-On" Part)

Instead of a simple "search and summarize" RAG, this is an **Agentic RAG**. You give the system a prompt, and a routing agent decides which tools to use.

1.  **The "Tailor My Pitch" Agent Flow:**
    *   *You say:* "I have an interview with AppFolio for the Enterprise Integration role. They want heavy Kafka and event-driven experience. How should I frame my background?"
    *   *Agent Action 1:* Does a SQL query on your **Structured Experience Data** to find any projects where you used Kafka or Pub/Sub. 
    *   *Agent Action 2:* Does a Vector Search on the **Unstructured Job Description** to understand AppFolio's specific needs.
    *   *Result:* The agent synthesizes a customized interview pitch highlighting your exact relevant experience against their exact requirements.

2.  **The "System Design Mock Interview" Flow:**
    *   *You say:* "Give me a mock system design interview question relevant to the PayPal Staff Engineer role."
    *   *Agent Action 1:* Vector Search on the PayPal JD to determine they need high-scale, fault-tolerant payment architecture experience. 
    *   *Agent Action 2:* Vector Search on the **Unstructured System Design Case Studies** to find a payments-related architecture prompt.
    *   *Result:* The agent acts as the interviewer and grades your architectural decisions based on standard patterns.

## Why this is great for you:
1.  **It's Personal:** You are building a tool that actively helps you get a job.
2.  **It's Agentic:** You get hands-on experience building an LLM router that chooses between SQL queries (structured) and Vector search (unstructured), which is exactly what Staff roles are asking for in GenAI platforms right now. 
3.  **It's Bounded:** You don't have to simulate a massive enterprise architecture. You just need a local SQLite DB, a local Chroma vector store, and LangChain/LlamaIndex.

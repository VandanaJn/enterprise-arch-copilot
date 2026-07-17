---
title: Enterprise Architecture Copilot
emoji: 🛠️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Enterprise Architecture Copilot

A multi-agent RAG incident copilot for a fictional payments SaaS (PayLane), built with
LangGraph, OpenAI, ChromaDB, and SQLite. This Space runs the FastAPI + SSE service; the
corpus (ChromaDB vectors + SQLite catalog) is baked into the image.

- `GET /healthz`: readiness (checks the baked data is present)
- `POST /chat`: ask the copilot; responses stream over Server-Sent Events
- `GET /metrics`: Prometheus metrics
- `GET /`: service info

This deployment is **API-only** for now; a browser chat UI is served at `/` in a later
iteration. Source and full docs: https://github.com/VandanaJn/enterprise-arch-copilot

# Deploying to Hugging Face Spaces

The whole app runs in one container: the FastAPI service, the LangGraph agent, the
DeBERTa injection classifier, and the on-disk data stores (ChromaDB + SQLite). The
only runtime dependency is the OpenAI API. A free CPU Space (2 vCPU / 16 GB RAM) is
enough.

## One-time setup

1. **Generate the data locally** (needs your OpenAI key), because it is not baked
   into the image and the Space should boot without spending embedding tokens:

   ```bash
   make setup   # writes docs/, engineering_data.db, chroma_db/
   ```

2. **Create a Docker Space**: huggingface.co → New Space → SDK: **Docker** →
   Blank. Note the git URL it gives you.

3. **Add the Space as a remote and push the repo plus the generated data.**
   `chroma_db/` and `engineering_data.db` are gitignored in this project, so
   force-add them for the Space remote only (they are small and the corpus is
   fixed):

   ```bash
   git remote add space https://huggingface.co/spaces/<user>/<space-name>
   git add -f chroma_db engineering_data.db docs
   git commit -m "Add generated corpus for HF Space"
   git push space HEAD:main
   ```

   Keep these artifacts out of the GitHub remote; they belong only to the Space.

4. **Set secrets** in the Space UI (Settings → Variables and secrets):
   - `OPENAI_API_KEY` (required)
   - `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true` (optional, for live traces)
   - `EAC_RATE_LIMIT_PER_MIN=10` (recommended: the URL is public; this caps
     worst-case OpenAI spend per client IP)

## How the container adapts to Spaces

- **Port**: Spaces expect the app on `7860`. The image reads `$PORT` (default
  `8000`), and the Space sets `PORT=7860`, so no Dockerfile change is needed.
- **Injection model**: baked at build time (`INSTALL_INJECTION_MODEL=true`, the
  default) so startup needs no model download.
- **Health**: `GET /healthz` returns 503 until the data files are present; with the
  committed corpus it returns 200 immediately.

## Notes

- **Cold starts**: free Spaces sleep after inactivity, so the first request after a
  quiet period takes ~1 minute to wake. Acceptable for a portfolio demo.
- **Abuse**: the in-app rate limiter plus `EAC_MAX_INPUT_CHARS` (default 4000) are
  the guardrails against a public endpoint running up API cost. There is no auth;
  do not point it at a paid key without the rate limit set.
- **Regenerating the corpus**: re-run `make setup` locally and re-push the three
  artifacts to the Space remote.

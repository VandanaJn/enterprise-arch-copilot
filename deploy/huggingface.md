# Deploying to Hugging Face Spaces (via GitHub Actions)

The whole app runs in one container: the FastAPI service, the LangGraph agent, the
DeBERTa injection classifier, and the on-disk corpus (ChromaDB + SQLite). Hugging Face
builds the Docker image from the pushed repo, so no local Docker is needed. Deployment
is driven by the [`deploy-hf`](../.github/workflows/deploy-hf.yml) GitHub Actions
workflow, triggered manually.

## One-time setup

1. **Get a Hugging Face write token**: huggingface.co → Settings → Access Tokens →
   New token (role: Write).

2. **Add GitHub repo secrets** (Settings → Secrets and variables → Actions → Secrets):
   - `HF_TOKEN`: the write token above
   - `OPENAI_API_KEY`: used to generate the corpus in CI and set as the Space's
     runtime secret
   - `LANGSMITH_API_KEY`: optional, enables live tracing on the Space

3. **Add a GitHub repo variable** (same page → Variables):
   - `HF_SPACE_ID`: e.g. `your-hf-username/enterprise-arch-copilot`. The workflow
     creates this Space (private, Docker SDK) if it does not exist.

## Deploy

Actions → **Deploy to Hugging Face Space** → **Run workflow**. The workflow:

1. Restores or generates the corpus (`chroma_db/`, `engineering_data.db`, `docs/`).
   `actions/cache` keys it on the corpus inputs, so unchanged deploys spend no
   embedding tokens.
2. Creates the private Space if needed and sets its runtime secret (`OPENAI_API_KEY`)
   and variables (`PORT=7860`, `EAC_RATE_LIMIT_PER_MIN=10`, `EAC_WARM_INJECTION_DETECTOR=1`).
   If `LANGSMITH_API_KEY` is set, it also sets `LANGSMITH_TRACING=true`,
   `LANGSMITH_PROJECT` (default `enterprise-arch-copilot`), and `LANGSMITH_ENDPOINT`
   (default the hosted US endpoint). Override the last two by adding GitHub repo
   **variables** of the same name; you never add them as secrets (they are not credentials).
3. Uploads the app plus the baked corpus. Two files are swapped in for the Space:
   `README.md` gets HF frontmatter (`sdk: docker`, `app_port: 7860`), and
   `.dockerignore` is relaxed so the corpus lands in the build context (Spaces have
   no volume mount).

HF then builds the image and starts the container. First build takes a few minutes
(installs CPU torch + transformers and bakes the injection model).

## After deploy

- Check it: `curl https://<user>-<space>.hf.space/healthz` returns `{"status":"ok"}`.
  `POST /chat` streams an answer over SSE. The Space is API-only until the web chat UI
  ships (served at `/`).
- The Space is **private**. To make it public later: HF Space → Settings → Change
  visibility, or `HfApi(token=...).update_repo_settings(space_id, repo_type="space", private=False)`.
- Free Spaces sleep after inactivity, so the first request after a quiet period takes
  ~1 minute to wake.

## Notes

- **Abuse**: the in-app rate limiter (`EAC_RATE_LIMIT_PER_MIN`) plus `EAC_MAX_INPUT_CHARS`
  cap worst-case OpenAI spend on a public endpoint. Set an OpenAI usage limit too.
- **Corpus regeneration**: change the templates or generation scripts and re-run the
  workflow; the cache key changes, so it regenerates and redeploys.
- `huggingface_hub` is deploy-time tooling (installed only in the workflow); it is not
  a runtime dependency and is not in `requirements.txt`.

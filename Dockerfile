# Enterprise Architecture Copilot API image.
#
# Torch is installed from the CPU-only wheel index BEFORE requirements.txt so pip
# sees it satisfied and never pulls the multi-GB CUDA build. The DeBERTa injection
# classifier can be baked at build time (INSTALL_INJECTION_MODEL=true, default) for
# fast offline startup, or skipped (=false, used in CI) in which case it downloads
# on first use and the detector fails open until then.
#
# Data (chroma_db/, engineering_data.db, docs/) is NOT baked in: it is generated
# with the operator's OpenAI key. Mount it (docker-compose) or commit it to the
# deployment repo (Hugging Face Spaces); see deploy/huggingface.md.

FROM python:3.12-slim

ARG INSTALL_INJECTION_MODEL=true

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf-cache \
    PORT=8000

WORKDIR /app

RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install -r requirements.txt

# Bake the injection classifier into the image so startup needs no network.
COPY src/config.py src/config.py
RUN if [ "$INSTALL_INJECTION_MODEL" = "true" ]; then \
      python -c "from transformers import pipeline; import os; \
pipeline('text-classification', model=os.environ.get('EAC_PROMPT_INJECTION_MODEL', 'protectai/deberta-v3-base-prompt-injection-v2'))"; \
    fi

COPY . .

RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app /opt/hf-cache
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\", \"8000\")}/healthz')" || exit 1

CMD ["sh", "-c", "uvicorn src.api.app:app --host 0.0.0.0 --port ${PORT}"]

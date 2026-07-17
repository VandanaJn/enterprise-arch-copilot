"""Deploy the copilot to a private Hugging Face Docker Space.

Run by .github/workflows/deploy-hf.yml (manual trigger). Uses huggingface_hub
(deploy-time tooling, not a runtime dependency) to:
  1. create the Space if it doesn't exist (private, Docker SDK),
  2. set the Space's runtime secret (OPENAI_API_KEY) and variables (PORT, rate
     limit, warm-up),
  3. upload a staging dir = tracked repo files + generated corpus, with the HF
     Space README and a relaxed .dockerignore swapped in so the corpus bakes
     into the image (HF Spaces have no volume mount).

Required env: HF_TOKEN, HF_SPACE_ID (e.g. "user/space"), OPENAI_API_KEY.
Optional env: EAC_RATE_LIMIT_PER_MIN (default 10), LANGSMITH_API_KEY. When the
LangSmith key is set, LANGSMITH_PROJECT and LANGSMITH_ENDPOINT are also propagated
to the Space (defaulting to "enterprise-arch-copilot" and the hosted US endpoint).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Generated corpus that must ride along in the build context (gitignored, so not
# in `git ls-files`).
DATA_PATHS = ("chroma_db", "engineering_data.db", "docs")

# Tracked paths we don't want on the Space (CI config, not part of the app).
EXCLUDE_PREFIXES = (".github/", ".claude/")

SPACE_README_SRC = REPO_ROOT / "deploy" / "space_README.md"
SPACE_DOCKERIGNORE_SRC = REPO_ROOT / "deploy" / "dockerignore.space"


def tracked_files(repo_root: Path) -> list[str]:
    """Repo-relative POSIX paths of git-tracked files."""
    out = subprocess.check_output(["git", "ls-files"], cwd=repo_root, text=True)
    return [line.strip() for line in out.splitlines() if line.strip()]


def build_staging(
    repo_root: Path,
    staging: Path,
    tracked: list[str],
    *,
    data_paths: tuple[str, ...] = DATA_PATHS,
    exclude_prefixes: tuple[str, ...] = EXCLUDE_PREFIXES,
    readme_src: Path = SPACE_README_SRC,
    dockerignore_src: Path = SPACE_DOCKERIGNORE_SRC,
) -> Path:
    """Assemble the exact tree to upload to the Space. Pure filesystem work.

    Copies tracked files (minus excluded prefixes), overlays the generated corpus,
    then swaps README.md and .dockerignore for their Space variants. Returns
    `staging`. Raises FileNotFoundError if a required corpus path is missing.
    """
    staging.mkdir(parents=True, exist_ok=True)

    for rel in tracked:
        if rel.startswith(exclude_prefixes):
            continue
        src = repo_root / rel
        if not src.is_file():
            continue
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    for rel in data_paths:
        src = repo_root / rel
        if not src.exists():
            raise FileNotFoundError(
                f"Required corpus path missing: {src}. Run `python -m scripts.setup` first."
            )
        dest = staging / rel
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    # Space-specific overrides: HF frontmatter README, and a .dockerignore that
    # keeps the corpus in the build context.
    shutil.copy2(readme_src, staging / "README.md")
    shutil.copy2(dockerignore_src, staging / ".dockerignore")
    return staging


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"[deploy] ERROR: {name} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    from huggingface_hub import HfApi

    token = _require_env("HF_TOKEN")
    space_id = _require_env("HF_SPACE_ID")
    openai_key = _require_env("OPENAI_API_KEY")
    rate_limit = os.environ.get("EAC_RATE_LIMIT_PER_MIN", "10")

    api = HfApi(token=token)

    print(f"[deploy] Ensuring Space exists (private, docker): {space_id}")
    api.create_repo(
        repo_id=space_id,
        repo_type="space",
        space_sdk="docker",
        private=True,
        exist_ok=True,
    )

    print("[deploy] Setting Space variables and secret")
    api.add_space_variable(space_id, "PORT", "7860")
    api.add_space_variable(space_id, "EAC_RATE_LIMIT_PER_MIN", rate_limit)
    api.add_space_variable(space_id, "EAC_WARM_INJECTION_DETECTOR", "1")
    api.add_space_secret(space_id, "OPENAI_API_KEY", openai_key)
    if langsmith_key := os.environ.get("LANGSMITH_API_KEY", "").strip():
        # Non-secret tracing config: set as Space variables so traces land in the
        # right project/region. Defaults match the standard hosted LangSmith; a
        # GitHub repo variable of the same name overrides.
        api.add_space_secret(space_id, "LANGSMITH_API_KEY", langsmith_key)
        api.add_space_variable(space_id, "LANGSMITH_TRACING", "true")
        api.add_space_variable(
            space_id,
            "LANGSMITH_PROJECT",
            os.environ.get("LANGSMITH_PROJECT") or "enterprise-arch-copilot",
        )
        api.add_space_variable(
            space_id,
            "LANGSMITH_ENDPOINT",
            os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com",
        )

    with tempfile.TemporaryDirectory() as tmp:
        staging = build_staging(REPO_ROOT, Path(tmp) / "space", tracked_files(REPO_ROOT))
        print(f"[deploy] Uploading staging tree to {space_id}")
        api.upload_folder(
            folder_path=str(staging),
            repo_id=space_id,
            repo_type="space",
            commit_message="Deploy from GitHub Actions",
            delete_patterns="*",  # mirror the staging dir (drop files from prior deploys)
        )

    owner, name = space_id.split("/", 1)
    print(f"[deploy] Done. Space: https://huggingface.co/spaces/{space_id}")
    print(f"[deploy] Direct app URL: https://{owner}-{name}.hf.space")


if __name__ == "__main__":
    main()

"""Unit test for the HF Space staging builder (no network, no HF calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.deploy_hf_space import build_staging


def _make_repo(root: Path) -> list[str]:
    """Create a fake repo tree; return the 'tracked' file list."""
    (root / "src").mkdir()
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / "deploy").mkdir()
    (root / "docs" / "adrs").mkdir(parents=True)
    (root / "chroma_db").mkdir()

    (root / "README.md").write_text("original project readme", encoding="utf-8")
    (root / ".dockerignore").write_text("chroma_db\ndocs\nengineering_data.db\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")
    (root / "src" / "agent.py").write_text("# agent", encoding="utf-8")
    (root / ".github" / "workflows" / "ci.yml").write_text("name: CI", encoding="utf-8")
    (root / "deploy" / "space_README.md").write_text(
        "---\nsdk: docker\n---\nspace", encoding="utf-8"
    )
    (root / "deploy" / "dockerignore.space").write_text(".git\n.github\n", encoding="utf-8")

    # generated corpus (gitignored in the real repo, so not in tracked list)
    (root / "engineering_data.db").write_text("sqlite", encoding="utf-8")
    (root / "docs" / "adrs" / "001.md").write_text("doc", encoding="utf-8")
    (root / "chroma_db" / "chroma.sqlite3").write_text("vectors", encoding="utf-8")

    return ["README.md", ".dockerignore", "Dockerfile", "src/agent.py", ".github/workflows/ci.yml"]


def test_build_staging_swaps_and_includes_data(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    tracked = _make_repo(repo)
    staging = build_staging(
        repo,
        tmp_path / "staging",
        tracked,
        readme_src=repo / "deploy" / "space_README.md",
        dockerignore_src=repo / "deploy" / "dockerignore.space",
    )

    # README swapped to the HF Space version (has frontmatter)
    assert "sdk: docker" in (staging / "README.md").read_text(encoding="utf-8")
    # .dockerignore swapped to the relaxed Space version (no data exclusions)
    dockerignore = (staging / ".dockerignore").read_text(encoding="utf-8")
    assert "chroma_db" not in dockerignore

    # tracked code copied; CI config excluded
    assert (staging / "src" / "agent.py").exists()
    assert (staging / "Dockerfile").exists()
    assert not (staging / ".github").exists()

    # generated corpus overlaid so it bakes into the image
    assert (staging / "engineering_data.db").exists()
    assert (staging / "docs" / "adrs" / "001.md").exists()
    assert (staging / "chroma_db" / "chroma.sqlite3").exists()


def test_build_staging_errors_when_corpus_missing(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "deploy").mkdir()
    (repo / "deploy" / "space_README.md").write_text("space", encoding="utf-8")
    (repo / "deploy" / "dockerignore.space").write_text(".git", encoding="utf-8")
    (repo / "README.md").write_text("readme", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="chroma_db"):
        build_staging(
            repo,
            tmp_path / "staging",
            ["README.md"],
            readme_src=repo / "deploy" / "space_README.md",
            dockerignore_src=repo / "deploy" / "dockerignore.space",
        )

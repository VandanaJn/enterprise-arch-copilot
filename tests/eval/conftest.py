# No path overrides needed here. src.config exposes paths as functions that read
# EAC_* env vars at call time. Eval tests run against the real corpus by default
# (no sandbox env vars are set when `pytest tests/eval/` is invoked directly).
# The tests/conftest.py sandbox only applies when running the full test suite,
# in which case eval tests are excluded via --ignore=tests/eval anyway.

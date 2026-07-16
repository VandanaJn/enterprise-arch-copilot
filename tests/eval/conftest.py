# No fixtures needed here. src.config exposes paths as functions that read EAC_*
# env vars at call time. The unit-test sandbox in tests/conftest.py applies to every
# session (pytest loads ancestor conftests even for `pytest tests/eval/`), so
# test_langsmith_eval.py explicitly removes the EAC_* overrides in a module-scoped
# fixture; evals must run against the real corpus, not tests/test_data/.

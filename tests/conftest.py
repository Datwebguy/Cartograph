import pytest


@pytest.fixture(autouse=True)
def _local_model_preset(monkeypatch):
    # The Duck "local" preset insists on a model id. Tests never contact it (LLM call is scripted).
    monkeypatch.setenv("LOCAL_ANALYZER_MODEL_ID", "scripted-test-model")
    monkeypatch.setenv("LOCAL_ANALYZER_BASE_URL", "http://127.0.0.1:1/v1")

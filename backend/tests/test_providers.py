import httpx
import pytest

from app.ai.providers import gemini
from app.ai.providers.base import ProviderError
from app.core.config import settings

SECRET = "AIza-test-secret-key-value"


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", SECRET)
    monkeypatch.setattr(gemini.time, "sleep", lambda _s: None)


def _response(status, body=None):
    return httpx.Response(status, json=body, request=httpx.Request("POST", "https://example.test"))


def test_error_message_carries_status_and_googles_text_but_not_the_key(monkeypatch):
    monkeypatch.setattr(gemini.httpx, "post", lambda *a, **k: _response(404, {"error": {"message": "model is no longer available"}}))
    with pytest.raises(ProviderError) as err:
        gemini.GeminiLLM().generate_text("s", "p")
    assert "404" in str(err.value) and "no longer available" in str(err.value) and SECRET not in str(err.value)


def test_transient_overload_is_retried_once(monkeypatch):
    calls = []

    def post(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            return _response(503, {"error": {"message": "high demand"}})
        return _response(200, {"candidates": [{"content": {"parts": [{"text": "{\"ok\": true}"}]}}]})

    monkeypatch.setattr(gemini.httpx, "post", post)
    assert gemini.GeminiLLM().generate_json("s", "p") == {"ok": True}
    assert len(calls) == 2


def test_persistent_overload_gives_up_after_one_retry(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini.httpx, "post", lambda *a, **k: calls.append(1) or _response(503, {"error": {"message": "high demand"}}))
    with pytest.raises(ProviderError, match="503"):
        gemini.GeminiLLM().generate_text("s", "p")
    assert len(calls) == 2


def test_client_errors_are_not_retried(monkeypatch):
    calls = []
    monkeypatch.setattr(gemini.httpx, "post", lambda *a, **k: calls.append(1) or _response(400, {"error": {"message": "bad key"}}))
    with pytest.raises(ProviderError, match="400"):
        gemini.GeminiLLM().generate_text("s", "p")
    assert len(calls) == 1


def _ok():
    return _response(200, {"candidates": [{"content": {"parts": [{"text": "hi"}]}}]})


def test_thinking_is_disabled_for_speed_by_default(monkeypatch):
    sent = []
    monkeypatch.setattr(gemini.httpx, "post", lambda url, **k: sent.append(k["json"]) or _ok())
    assert gemini.GeminiLLM().generate_text("s", "p") == "hi"
    assert sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}


def test_model_that_rejects_thinking_config_is_retried_without_it(monkeypatch):
    sent = []

    def post(url, **k):
        sent.append(dict(k["json"]["generationConfig"]))
        if "thinkingConfig" in k["json"]["generationConfig"]:
            return _response(400, {"error": {"message": "Thinking is not supported by this model"}})
        return _ok()

    monkeypatch.setattr(gemini.httpx, "post", post)
    assert gemini.GeminiLLM().generate_text("s", "p") == "hi"
    assert "thinkingConfig" in sent[0] and "thinkingConfig" not in sent[1]


def test_thinking_setting_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(settings, "gemini_disable_thinking", False)
    sent = []
    monkeypatch.setattr(gemini.httpx, "post", lambda url, **k: sent.append(k["json"]) or _ok())
    gemini.GeminiLLM().generate_text("s", "p")
    assert "thinkingConfig" not in sent[0]["generationConfig"]

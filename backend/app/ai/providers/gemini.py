import json
import math
import time

import httpx

from app.ai.providers.base import ProviderError
from app.core.config import settings

BASE = "https://generativelanguage.googleapis.com/v1beta"


def _headers() -> dict[str, str]:
    if not settings.gemini_api_key:
        raise ProviderError("GEMINI_API_KEY is not configured")
    return {"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"}


def _post(path: str, payload: dict) -> dict:
    """POST with one retry for transient overload (429/503). Errors carry Google's own message, never the key."""
    last: httpx.HTTPError | None = None
    for attempt in range(2):
        try:
            resp = httpx.post(f"{BASE}/{path}", headers=_headers(), json=payload, timeout=settings.llm_timeout_seconds)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as exc:
            last = exc
            if exc.response.status_code in (429, 503) and attempt == 0:
                time.sleep(1.0)
                continue
            raise ProviderError(f"Gemini HTTP {exc.response.status_code}: {_api_message(exc.response)}") from exc
        except httpx.HTTPError as exc:
            last = exc
            raise ProviderError(f"Gemini request failed: {exc.__class__.__name__}") from exc
    raise ProviderError(f"Gemini request failed: {last.__class__.__name__}")


def _api_message(resp: httpx.Response) -> str:
    try:
        return str(resp.json()["error"]["message"])[:300]
    except (ValueError, KeyError, TypeError):
        return resp.reason_phrase


class GeminiLLM:
    name = "gemini"

    def _generate(self, system: str, prompt: str, as_json: bool) -> str:
        config: dict = {"temperature": 0.0}
        if as_json:
            config["responseMimeType"] = "application/json"
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": config,
        }
        path = f"models/{settings.gemini_model}:generateContent"
        if settings.gemini_disable_thinking:
            # Extraction and explanation are simple structured tasks; reasoning tokens only add seconds of latency.
            config["thinkingConfig"] = {"thinkingBudget": 0}
            try:
                data = _post(path, payload)
            except ProviderError as exc:
                if "HTTP 400" not in str(exc) or "thinking" not in str(exc).lower():
                    raise
                del config["thinkingConfig"]  # this model doesn't accept the setting: retry as-is
                data = _post(path, payload)
        else:
            data = _post(path, payload)
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError("Unexpected Gemini response shape") from exc

    def generate_json(self, system: str, prompt: str) -> dict:
        text = self._generate(system, prompt, as_json=True)
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("Gemini returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ProviderError("Gemini JSON was not an object")
        return value

    def generate_text(self, system: str, prompt: str) -> str:
        return self._generate(system, prompt, as_json=False).strip()


class GeminiEmbeddings:
    # Measured on gemini-embedding-001 with a 17-product catalogue: unrelated queries ('sandals', 'banana') score
    # their best product 0.53-0.60; relevant ones 0.63-0.71. Re-measure when the catalogue grows.
    min_similarity = 0.615

    def __init__(self) -> None:
        self.model_name = settings.gemini_embedding_model
        self.dim = settings.embedding_dim

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        task = "RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT"
        model = f"models/{self.model_name}"
        requests = [
            {
                "model": model,
                "content": {"parts": [{"text": t}]},
                "taskType": task,
                "outputDimensionality": self.dim,
            }
            for t in texts
        ]
        data = _post(f"{model}:batchEmbedContents", {"requests": requests})
        try:
            vectors = [e["values"] for e in data["embeddings"]]
        except (KeyError, TypeError) as exc:
            raise ProviderError("Unexpected Gemini embedding response") from exc
        # Truncated (Matryoshka) embeddings are not unit length; cosine search expects normalised vectors.
        return [_normalise(v) for v in vectors]


def _normalise(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / norm for x in v]

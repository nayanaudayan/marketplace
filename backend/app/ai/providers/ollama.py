import json

import httpx

from app.ai.providers.base import ProviderError
from app.core.config import settings


def _post(path: str, payload: dict) -> dict:
    try:
        resp = httpx.post(f"{settings.ollama_base_url}{path}", json=payload, timeout=settings.llm_timeout_seconds)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise ProviderError(f"Ollama request failed: {exc.__class__.__name__}") from exc


class OllamaLLM:
    name = "ollama"

    def _chat(self, system: str, prompt: str, as_json: bool) -> str:
        payload = {
            "model": settings.ollama_model,
            "stream": False,
            "options": {"temperature": 0},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
        }
        if as_json:
            payload["format"] = "json"
        data = _post("/api/chat", payload)
        try:
            return data["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ProviderError("Unexpected Ollama response shape") from exc

    def generate_json(self, system: str, prompt: str) -> dict:
        try:
            value = json.loads(self._chat(system, prompt, as_json=True))
        except json.JSONDecodeError as exc:
            raise ProviderError("Ollama returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ProviderError("Ollama JSON was not an object")
        return value

    def generate_text(self, system: str, prompt: str) -> str:
        return self._chat(system, prompt, as_json=False).strip()


class OllamaEmbeddings:
    min_similarity = 0.45  # untuned guess: measure like Gemini's (see gemini.py) before relying on it

    def __init__(self) -> None:
        self.model_name = settings.ollama_embedding_model
        self.dim = settings.embedding_dim

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        data = _post("/api/embed", {"model": self.model_name, "input": texts})
        vectors = data.get("embeddings")
        if not vectors or len(vectors) != len(texts):
            raise ProviderError("Unexpected Ollama embedding response")
        if any(len(v) != self.dim for v in vectors):
            raise ProviderError(
                f"Ollama model '{self.model_name}' returned {len(vectors[0])}-dim vectors but EMBEDDING_DIM={self.dim}"
            )
        return vectors

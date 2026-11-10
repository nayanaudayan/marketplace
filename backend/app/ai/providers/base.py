from typing import Protocol


class ProviderError(Exception):
    """Any failure talking to an LLM/embedding backend. Callers degrade gracefully on this."""


class LLMProvider(Protocol):
    name: str

    def generate_json(self, system: str, prompt: str) -> dict:
        """Returns a parsed JSON object. Raises ProviderError on transport or parse failure."""

    def generate_text(self, system: str, prompt: str) -> str:
        ...


class EmbeddingProvider(Protocol):
    model_name: str
    dim: int
    # Cosine similarity below which a result with no keyword hit is considered unrelated (untuned defaults).
    min_similarity: float

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        ...

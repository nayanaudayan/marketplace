"""Offline providers for development and tests: no network, deterministic, no API keys."""
import hashlib
import math
import re

from app.ai.providers.base import ProviderError
from app.core.config import settings

# Tiny synonym table so the dev embedder shows some "semantic" behaviour (coding ~ programming).
SYNONYMS = {
    "coding": "programming",
    "code": "programming",
    "developer": "programming",
    "development": "programming",
    "software": "programming",
    "notebook": "laptop",
    "ultrabook": "laptop",
    "lightweight": "light",
    "portable": "light",
    "slim": "light",
    "phone": "smartphone",
    "mobile": "smartphone",
    "earphones": "headphones",
    "earbuds": "headphones",
    "headset": "headphones",
}
STOPWORDS = {"a", "an", "the", "for", "with", "and", "of", "to", "in", "on", "i", "need", "want", "good", "best", "me", "is"}


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if tok in STOPWORDS:
            continue
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]
        tokens.append(SYNONYMS.get(tok, tok))
    return tokens


class HashEmbeddings:
    """Signed feature hashing of unigrams+bigrams into a fixed-size unit vector. Captures lexical overlap only."""

    min_similarity = 0.12

    def __init__(self) -> None:
        self.model_name = "hash-v1"
        self.dim = settings.embedding_dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        tokens = tokenize(text)
        grams = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for g in grams:
            h = int.from_bytes(hashlib.blake2b(g.encode(), digest_size=8).digest(), "big")
            vec[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class NoLLM:
    """Selected when LLM_PROVIDER=mock. Callers fall back to rule-based extraction and templated explanations."""

    name = "mock"

    def generate_json(self, system: str, prompt: str) -> dict:
        raise ProviderError("No LLM configured (LLM_PROVIDER=mock)")

    def generate_text(self, system: str, prompt: str) -> str:
        raise ProviderError("No LLM configured (LLM_PROVIDER=mock)")

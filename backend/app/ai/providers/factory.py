from functools import lru_cache

from app.ai.providers.base import EmbeddingProvider, LLMProvider
from app.ai.providers.gemini import GeminiEmbeddings, GeminiLLM
from app.ai.providers.local import HashEmbeddings, NoLLM
from app.ai.providers.ollama import OllamaEmbeddings, OllamaLLM
from app.core.config import settings


@lru_cache
def get_llm_provider() -> LLMProvider:
    providers = {"gemini": GeminiLLM, "ollama": OllamaLLM, "mock": NoLLM}
    try:
        return providers[settings.llm_provider]()
    except KeyError:
        raise ValueError(f"Unknown LLM_PROVIDER '{settings.llm_provider}'") from None


@lru_cache
def get_embedding_provider() -> EmbeddingProvider:
    providers = {"gemini": GeminiEmbeddings, "ollama": OllamaEmbeddings, "hash": HashEmbeddings}
    try:
        provider = providers[settings.embedding_provider]()
    except KeyError:
        raise ValueError(f"Unknown EMBEDDING_PROVIDER '{settings.embedding_provider}'") from None
    if settings.semantic_min_similarity:  # explicit override of the provider's measured default
        provider.min_similarity = settings.semantic_min_similarity
    return provider

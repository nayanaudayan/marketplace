"""Relevance ranking. Hard constraints (budget, stock, specs) are enforced in SQL *before* this runs, so a high
score can never resurrect an ineligible product. Weights are starting points: tune them with the benchmark set."""
from dataclasses import dataclass

from app.ai.agents.query_understanding import Preference
from app.ai.retrieval.hybrid import Candidate
from app.modules.products.models import Product

WEIGHTS = {"semantic": 0.40, "keyword": 0.20, "spec": 0.10, "category": 0.10, "quality": 0.10, "preference": 0.10}


@dataclass
class Scored:
    product: Product
    candidate: Candidate
    score: float


def _quality(avg_rating: float | None, review_count: int) -> float:
    """Rating shrunk toward a neutral prior so one 5-star review doesn't beat 200 reviews at 4.6."""
    prior, weight = 3.5, 5
    avg = avg_rating if avg_rating is not None else prior
    return ((avg * review_count + prior * weight) / (review_count + weight)) / 5.0


def _number(product: Product, key: str) -> float | None:
    value = (product.specifications or {}).get(key)
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def preference_scores(products: list[Product], preferences: list[Preference]) -> dict[int, float]:
    """0..1 per product from the *real* listing values: for 'lightweight' the lightest candidate scores 1 and the
    heaviest 0. Products without the field, or fields where every candidate is equal, get a neutral 0.5."""
    if not preferences:
        return {}
    per_key: dict[str, tuple[float, float]] = {}
    for pref in preferences:
        values = [v for p in products if (v := _number(p, pref.key)) is not None]
        if values:
            per_key[pref.key] = (min(values), max(values))
    scores = {}
    for p in products:
        parts = []
        for pref in preferences:
            v, bounds = _number(p, pref.key), per_key.get(pref.key)
            if v is None or bounds is None or bounds[0] == bounds[1]:
                parts.append(0.5)
                continue
            fraction = (v - bounds[0]) / (bounds[1] - bounds[0])
            parts.append(1.0 - fraction if pref.direction == "asc" else fraction)
        scores[p.id] = sum(parts) / len(parts)
    return scores


def rank(
    candidates: list[Candidate],
    products: dict[int, Product],
    keywords: list[str],
    category_matched: bool,
    ratings: dict[int, tuple[float, int]],
    min_semantic: float,
    preferences: list[Preference] | None = None,
) -> list[Scored]:
    max_kw = max((c.keyword for c in candidates), default=0.0) or 1.0
    prefs = preference_scores([products[c.product_id] for c in candidates if c.product_id in products], preferences or [])
    scored: list[Scored] = []
    for c in candidates:
        product = products.get(c.product_id)
        if product is None:
            continue
        semantic = max(c.semantic, 0.0) if c.semantic is not None else 0.0
        # Without a category constraint the vector list contains the whole catalogue; drop unrelated tail items.
        if not category_matched and c.keyword == 0 and semantic < min_semantic:
            continue
        haystack = f"{product.name} {product.brand or ''} {product.description} {product.specifications}".lower()
        spec = (sum(1 for k in keywords if k in haystack) / len(keywords)) if keywords else 0.0
        avg, count = ratings.get(product.id, (None, 0))
        score = (
            WEIGHTS["semantic"] * semantic
            + WEIGHTS["keyword"] * (c.keyword / max_kw)
            + WEIGHTS["spec"] * spec
            + WEIGHTS["category"] * (1.0 if category_matched else 0.0)
            + WEIGHTS["quality"] * _quality(avg, count)
            + WEIGHTS["preference"] * prefs.get(product.id, 0.0)
        )
        scored.append(Scored(product, c, score))
    return sorted(scored, key=lambda s: (-s.score, s.product.id))

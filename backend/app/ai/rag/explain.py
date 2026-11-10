"""RAG step: the LLM is shown only verified, database-sourced facts and asked to explain the match.
If it is unavailable or returns something unusable, deterministic templates built from the same facts are used."""
import logging
from decimal import Decimal

from app.ai.agents.query_understanding import ExtractedRequirements
from app.ai.prompts import explanation
from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.retrieval.catalog import format_value, humanize
from app.ai.retrieval.verify import Offer
from app.modules.products.models import Product

log = logging.getLogger(__name__)


def _inr(value: Decimal) -> str:
    return f"₹{value:,.0f}"


def _spec_value(product: Product, key: str):
    return (product.specifications or {}).get(key)


def template_reason(
    req: ExtractedRequirements, product: Product, offer: Offer, best: dict[str, float] | None = None
) -> str:
    """Built only from this product's real listing data. `best` maps preference key -> best value among the results."""
    bits = []
    if req.max_price is not None:
        bits.append(f"within your budget at {_inr(offer.price)}")
    else:
        bits.append(f"available at {_inr(offer.price)}")

    for s in req.specs:
        value = _spec_value(product, s.key)
        if value is None:
            continue
        if isinstance(s.value, bool):
            bits.append(humanize(s.key).lower() if s.value else f"no {humanize(s.key).lower()}")
        elif isinstance(s.value, str):
            bits.append(f"{humanize(s.key).lower()} {value}")
        else:
            wanted = {">=": "meets your", "<=": "within your", "==": "matches your"}[s.op]
            limit = {">=": "minimum", "<=": "limit", "==": "requirement"}[s.op]
            bits.append(f"{humanize(s.key)} {format_value(s.key, value)} {wanted} {format_value(s.key, s.value)} {limit}")

    for p in req.preferences:
        value = _spec_value(product, p.key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            text = f"{humanize(p.key).lower()} {format_value(p.key, value)}"
            if best and best.get(p.key) == value:
                text += " (best among these)"
            bits.append(text)

    if req.usage:
        bits.append(f"suited to {req.usage}")
    bits.append(f"{offer.stock} in stock from {offer.seller_name}")
    reason = "; ".join(bits)
    return reason[0].upper() + reason[1:] + "."


def best_values(req: ExtractedRequirements, items: list[tuple[Product, Offer]]) -> dict[str, float]:
    """For each preference, the best real value among the displayed products (lowest for 'asc', highest for 'desc')."""
    best: dict[str, float] = {}
    for pref in req.preferences:
        values = [
            float(v) for p, _ in items if isinstance(v := _spec_value(p, pref.key), (int, float)) and not isinstance(v, bool)
        ]
        if len(values) > 1 and len(set(values)) > 1:
            best[pref.key] = min(values) if pref.direction == "asc" else max(values)
    return best


def _facts(product: Product, offer: Offer) -> dict:
    return {
        "product_id": product.id,
        "name": product.name,
        "brand": product.brand,
        "price_inr": str(offer.price),
        "stock": offer.stock,
        "seller": offer.seller_name,
        "specifications": product.specifications or {},
        "description": (product.description or "")[:200],
    }


def explain_results(
    llm: LLMProvider, query: str, req: ExtractedRequirements, items: list[tuple[Product, Offer]]
) -> tuple[str, dict[int, str]]:
    """Returns (overall explanation, {product_id: reason}). Always returns a reason for every item."""
    best = best_values(req, items)
    fallback = {p.id: template_reason(req, p, o, best) for p, o in items}
    if not items:
        return "No available products matched all of your requirements. Try relaxing the budget or specs.", {}
    summary = f"Found {len(items)} matching product{'s' if len(items) != 1 else ''} that meet your requirements and are in stock."
    try:
        raw = llm.generate_json(
            explanation.SYSTEM,
            explanation.build_prompt(query, req.model_dump(mode="json"), [_facts(p, o) for p, o in items]),
        )
        reasons_raw = raw.get("reasons")
        text = raw.get("explanation")
        if not isinstance(reasons_raw, dict) or not isinstance(text, str):
            raise ProviderError("malformed explanation payload")
        reasons = dict(fallback)
        for key, value in reasons_raw.items():
            if str(key).isdigit() and int(key) in fallback and isinstance(value, str) and value.strip():
                reasons[int(key)] = value.strip()[:300]
        return text.strip()[:500] or summary, reasons
    except (ProviderError, AttributeError, ValueError) as exc:
        log.warning("LLM explanation unavailable (%s); using templates", exc)
        return summary, fallback

import logging
import re
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai.agents.query_understanding import ExtractedRequirements, SpecFilter, extract_requirements, merge_context
from app.ai.prompts import explanation as explain_prompts
from app.ai.providers.base import ProviderError
from app.ai.providers.factory import get_embedding_provider, get_llm_provider
from app.ai.ranking.ranker import rank
from app.ai.rag.explain import explain_results
from app.ai.retrieval.catalog import describe_preference, describe_spec, load_spec_catalog
from app.ai.retrieval.hybrid import hybrid_search
from app.ai.retrieval.verify import best_offers
from app.ai.tools.registry import CompareArgs, call_tool
from app.core.cache import rate_limit
from app.core.config import settings
from app.modules.ai_search.models import AIConversation, AIMessage
from app.modules.ai_search.schemas import AIProduct, AISearchRequest, AISearchResponse, CompareResponse
from app.modules.categories.models import Category
from app.modules.categories.router import category_and_descendants
from app.modules.products.filters import ProductFilters, SpecClause
from app.modules.products.models import Product
from app.modules.products.schemas import ProductDetail
from app.modules.products.service import build_cards
from app.modules.reviews.models import Review
from app.modules.users.models import User

log = logging.getLogger(__name__)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower()).rstrip("s")


def resolve_category(db: Session, name: str | None) -> Category | None:
    """Maps an LLM/heuristic category string to a real category. Unknown names are ignored, never trusted."""
    if not name:
        return None
    target = _norm(name)
    for c in db.scalars(select(Category)):
        if _norm(c.name) == target:
            return c
    return None


def get_conversation(db: Session, conversation_id: int, user: User) -> AIConversation:
    conv = db.get(AIConversation, conversation_id)
    if conv is None or conv.user_id != user.id:  # 404 either way: don't reveal other users' conversations
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return conv


def run_search(db: Session, user: User | None, req: AISearchRequest, client_key: str) -> AISearchResponse:
    if not rate_limit(f"ai-search:{client_key}", settings.ai_search_rate_limit_per_minute):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many searches; please slow down")

    conversation = None
    if user is not None:
        conversation = get_conversation(db, req.conversation_id, user) if req.conversation_id else None
        if conversation is None:
            conversation = AIConversation(user_id=user.id, title=req.query[:80], context={})
            db.add(conversation)
            db.flush()
    previous = conversation.context if conversation else None

    llm = get_llm_provider()
    categories = list(db.scalars(select(Category.name)))
    brands = list(db.scalars(select(Product.brand).where(Product.brand.is_not(None), Product.status == "active").distinct()))
    catalog = load_spec_catalog(db)  # the spec fields the listings actually have

    # 1) understand (grounded in real listing fields) -> merge with conversation context -> explicit UI filters win
    extracted = extract_requirements(llm, req.query, categories, brands, catalog, previous)
    requirements = merge_context(previous, extracted)
    if req.filters:
        overrides = req.filters.model_dump(exclude_none=True)
        ram = overrides.pop("minimum_ram_gb", None)
        requirements = ExtractedRequirements.model_validate({**requirements.model_dump(), **overrides})
        if ram is not None:  # an explicit RAM filter replaces any RAM requirement found in the text
            specs = [s for s in requirements.specs if s.key != "ram_gb"] + [SpecFilter(key="ram_gb", op=">=", value=ram)]
            requirements = requirements.model_copy(update={"specs": specs})

    category = resolve_category(db, requirements.category)
    brand = next((b for b in brands if requirements.brand and b.lower() == requirements.brand.lower()), None)
    if category is not None and requirements.preferences:
        # a soft wish only makes sense on a field this kind of product actually has (no phone-battery wish for laptops)
        names = set(db.scalars(select(Category.name).where(Category.id.in_(category_and_descendants(db, category.id)))))
        relevant = [p for p in requirements.preferences if names & set(catalog[p.key].categories)]
        requirements = requirements.model_copy(update={"preferences": relevant})
    filters = ProductFilters(
        category_id=category.id if category else None,
        brand=brand,
        min_price=requirements.min_price,
        max_price=requirements.max_price,
        in_stock=True,  # unavailable products are never presented as valid matches
        specs=[SpecClause(s.key, s.op, s.value) for s in requirements.specs],
    )

    # 2) embed the query (best effort: keyword + filters still work without it)
    embedder = get_embedding_provider()
    query_text = " ".join(filter(None, [req.query, requirements.usage]))
    try:
        query_embedding = embedder.embed([query_text], is_query=True)[0]
    except (ProviderError, ValueError) as exc:
        log.warning("query embedding failed (%s); falling back to keyword search", exc)
        query_embedding = None

    # 3) hybrid retrieval -> rank -> verify live price/stock
    candidates = hybrid_search(db, req.query, requirements.keywords, filters, query_embedding)
    products = {
        p.id: p
        for p in db.scalars(select(Product).options(selectinload(Product.images)).where(Product.id.in_([c.product_id for c in candidates])))
    }
    ratings = {
        pid: (float(avg), cnt)
        for pid, avg, cnt in db.execute(
            select(Review.product_id, func.avg(Review.rating), func.count(Review.id))
            .where(Review.product_id.in_(list(products)))
            .group_by(Review.product_id)
        )
    }
    ranked = rank(
        candidates, products, requirements.keywords, category is not None, ratings, embedder.min_similarity,
        requirements.preferences,
    )
    offers = best_offers(db, [s.product.id for s in ranked], requirements.min_price, requirements.max_price, require_stock=True)
    verified = [(s, offers[s.product.id]) for s in ranked if s.product.id in offers]

    if req.sort_by == "price_asc":
        verified.sort(key=lambda t: (t[1].price, t[0].product.id))
    elif req.sort_by == "price_desc":
        verified.sort(key=lambda t: (-t[1].price, t[0].product.id))

    total = len(verified)
    start = (req.page - 1) * req.page_size
    page = verified[start : start + req.page_size]

    # 4) explain using only verified facts
    explanation, reasons = explain_results(llm, req.query, requirements, [(s.product, o) for s, o in page])

    cards = {c.id: c for c in build_cards(db, [s.product for s, _ in page])}
    result = [
        AIProduct(
            **cards[s.product.id].model_dump(),
            listing_id=o.listing_id,
            price=o.price,
            stock=o.stock,
            seller_name=o.seller_name,
            score=round(s.score, 4),
            match_reason=reasons[s.product.id],
        )
        for s, o in page
    ]

    if conversation is not None:
        conversation.context = requirements.model_dump(mode="json")
        db.add(AIMessage(conversation_id=conversation.id, role="user", message=req.query))
        db.add(AIMessage(conversation_id=conversation.id, role="assistant", message=explanation))
        db.commit()

    return AISearchResponse(
        query=req.query,
        conversation_id=conversation.id if conversation else None,
        extracted_filters=public_filters(requirements),
        total=total,
        explanation=explanation,
        products=result,
    )


def public_filters(req: ExtractedRequirements) -> dict:
    """What the UI shows as chips. Spec requirements and preferences are rendered as readable phrases."""
    data = req.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    data.pop("specs", None)
    data.pop("preferences", None)
    if req.specs:
        data["specs"] = [describe_spec(s.key, s.op, s.value) for s in req.specs]
    if req.preferences:
        data["preferences"] = [describe_preference(p.key, p.direction) for p in req.preferences]
    return data


def compare(db: Session, product_ids: list[int]) -> CompareResponse:
    details = [ProductDetail.model_validate(d) for d in call_tool(db, "compare_products", CompareArgs(product_ids=product_ids).model_dump())]
    if len(details) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Need at least two available products to compare")

    facts = [
        {"name": d.name, "brand": d.brand, "price_inr": str(d.min_price), "rating": d.avg_rating, "in_stock": d.in_stock, "specifications": d.specifications}
        for d in details
    ]
    try:
        summary = get_llm_provider().generate_text(explain_prompts.COMPARE_SYSTEM, explain_prompts.build_compare_prompt(facts))
    except ProviderError:
        summary = _template_comparison(details)
    return CompareResponse(products=details, summary=summary)


def _template_comparison(details: list[ProductDetail]) -> str:
    priced = [d for d in details if d.min_price is not None]
    parts = []
    if priced:
        cheapest = min(priced, key=lambda d: d.min_price or Decimal("0"))
        parts.append(f"{cheapest.name} is the lowest priced at ₹{cheapest.min_price:,.0f}.")
    rated = [d for d in details if d.avg_rating is not None]
    if rated:
        best = max(rated, key=lambda d: d.avg_rating or 0)
        parts.append(f"{best.name} has the highest customer rating ({best.avg_rating}/5).")
    keys = sorted({k for d in details for k in d.specifications})
    differing = [k for k in keys if len({str(d.specifications.get(k)) for d in details}) > 1]
    if differing:
        parts.append("Key differences: " + ", ".join(differing[:6]) + ".")
    return " ".join(parts) or "These products have similar specifications."

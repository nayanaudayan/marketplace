"""Hybrid retrieval: hard SQL filters -> (vector similarity + keyword full-text) -> reciprocal-rank fusion."""
import logging
import re
from dataclasses import dataclass

from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import Session

from app.ai.providers.local import STOPWORDS
from app.modules.ai_search.models import ProductEmbedding
from app.modules.products.filters import ProductFilters, build_filter_clauses
from app.modules.products.models import FTS_EXPRESSION, Product

log = logging.getLogger(__name__)
RRF_K = 60
CANDIDATE_LIMIT = 100


@dataclass
class Candidate:
    product_id: int
    semantic: float | None = None  # cosine similarity, None when the product has no embedding / vector search skipped
    keyword: float = 0.0  # ts_rank_cd
    rrf: float = 0.0


def _tsquery_terms(text: str, keywords: list[str]) -> str:
    """Builds an OR-query (any term may match) from sanitised alphanumeric tokens only."""
    tokens = []
    for source in [text, *keywords]:
        for tok in re.findall(r"[a-z0-9]+", source.lower()):
            if len(tok) > 2 and tok not in STOPWORDS and tok not in tokens:
                tokens.append(tok)
    return " | ".join(tokens[:20])


def hybrid_search(
    db: Session,
    query_text: str,
    keywords: list[str],
    filters: ProductFilters,
    query_embedding: list[float] | None,
    limit: int = CANDIDATE_LIMIT,
) -> list[Candidate]:
    clauses = build_filter_clauses(db, filters)
    candidates: dict[int, Candidate] = {}

    def get(pid: int) -> Candidate:
        return candidates.setdefault(pid, Candidate(pid))

    # 1) vector search over the already-filtered set (unembedded products sort last)
    if query_embedding is not None:
        distance = ProductEmbedding.embedding.cosine_distance(query_embedding)
        rows = db.execute(
            select(Product.id, distance)
            .outerjoin(ProductEmbedding, ProductEmbedding.product_id == Product.id)
            .where(*clauses)
            .order_by(distance.asc().nulls_last(), Product.id)
            .limit(limit)
        ).all()
        for rank, (pid, dist) in enumerate(rows):
            c = get(pid)
            c.semantic = None if dist is None else 1.0 - float(dist)
            c.rrf += 1.0 / (RRF_K + rank)

    # 2) keyword search (PostgreSQL full-text, OR semantics for natural-language queries)
    terms = _tsquery_terms(query_text, keywords)
    if terms:
        tsquery = func.to_tsquery("english", terms)
        tsvector = literal_column(FTS_EXPRESSION)
        rank_expr = func.ts_rank_cd(tsvector, tsquery)
        rows = db.execute(
            select(Product.id, rank_expr).where(*clauses, tsvector.op("@@")(tsquery)).order_by(rank_expr.desc(), Product.id).limit(limit)
        ).all()
        for rank, (pid, score) in enumerate(rows):
            c = get(pid)
            c.keyword = float(score)
            c.rrf += 1.0 / (RRF_K + rank)

    # 3) if neither signal produced anything (e.g. embedding provider down and no usable keywords), the hard
    #    filters alone still define a valid result set.
    if not candidates:
        for rank, (pid,) in enumerate(db.execute(select(Product.id).where(*clauses).order_by(Product.id.desc()).limit(limit))):
            get(pid).rrf = 1.0 / (RRF_K + rank)

    return sorted(candidates.values(), key=lambda c: c.rrf, reverse=True)

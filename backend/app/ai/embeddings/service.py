import hashlib
import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai.providers.factory import get_embedding_provider
from app.modules.ai_search.models import ProductEmbedding
from app.modules.categories.models import Category
from app.modules.products.models import Product

log = logging.getLogger(__name__)


def build_product_text(product: Product, category_name: str) -> str:
    """Searchable text only. Price and stock are deliberately excluded: they change often and must be
    read live from the database, never from an embedding."""
    specs = "\n".join(f"{k}: {v}" for k, v in sorted((product.specifications or {}).items()))
    parts = [
        f"Product: {product.name}",
        f"Brand: {product.brand}" if product.brand else "",
        f"Category: {category_name}",
        f"Description: {product.description}",
        f"Specifications:\n{specs}" if specs else "",
    ]
    return "\n".join(p for p in parts if p)


def content_hash(text: str, model_name: str) -> str:
    return hashlib.sha256(f"{model_name}\n{text}".encode()).hexdigest()


def index_product(db: Session, product_id: int) -> bool:
    """Creates/refreshes a product's embedding. Returns True if a new vector was computed."""
    product = db.get(Product, product_id)
    if product is None or product.status != "active":
        db.execute(delete(ProductEmbedding).where(ProductEmbedding.product_id == product_id))
        db.commit()
        return False

    provider = get_embedding_provider()
    category_name = db.scalar(select(Category.name).where(Category.id == product.category_id)) or ""
    text = build_product_text(product, category_name)
    digest = content_hash(text, provider.model_name)

    existing = db.scalar(select(ProductEmbedding).where(ProductEmbedding.product_id == product_id))
    if existing and existing.content_hash == digest:
        return False

    vector = provider.embed([text])[0]
    if existing:
        existing.embedding, existing.embedding_model, existing.content_hash = vector, provider.model_name, digest
    else:
        db.add(ProductEmbedding(product_id=product_id, embedding=vector, embedding_model=provider.model_name, content_hash=digest))
    db.commit()
    return True


def reindex_all(db: Session) -> int:
    ids = db.scalars(select(Product.id).where(Product.status == "active")).all()
    return sum(1 for pid in ids if index_product(db, pid))

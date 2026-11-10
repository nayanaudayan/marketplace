import logging

from app.core.config import settings
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.index_product", bind=True, max_retries=3, default_retry_delay=30)
def index_product(self, product_id: int) -> bool:
    from app.ai.embeddings.service import index_product as run
    from app.core.database import SessionLocal

    with SessionLocal() as db:
        try:
            return run(db, product_id)
        except Exception as exc:  # provider hiccup: retry with backoff, product stays keyword-searchable meanwhile
            log.warning("embedding product %s failed: %s", product_id, exc)
            if settings.celery_eager:
                return False
            raise self.retry(exc=exc)


@celery_app.task(name="app.workers.tasks.release_expired_orders")
def release_expired_orders() -> int:
    from app.core.database import SessionLocal
    from app.modules.orders.service import expire_pending_orders

    with SessionLocal() as db:
        return expire_pending_orders(db)


def enqueue_product_indexing(product_id: int) -> None:
    """Never lets an indexing problem fail the seller's request."""
    try:
        index_product.delay(product_id)
    except Exception as exc:
        log.warning("could not enqueue indexing for product %s: %s", product_id, exc)

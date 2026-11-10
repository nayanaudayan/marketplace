from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.cache import cache_get, cache_set
from app.core.database import get_db
from app.modules.categories.models import Category

router = APIRouter(prefix="/categories", tags=["categories"])
CACHE_KEY = "categories:all"


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None = None
    parent_category_id: int | None = None


def category_and_descendants(db: Session, category_id: int) -> list[int]:
    rows = db.execute(select(Category.id, Category.parent_category_id)).all()
    children: dict[int | None, list[int]] = {}
    for cid, parent in rows:
        children.setdefault(parent, []).append(cid)
    result, stack = [], [category_id]
    while stack:
        current = stack.pop()
        result.append(current)
        stack.extend(children.get(current, []))
    return result


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    cached = cache_get(CACHE_KEY)
    if cached is not None:
        return cached
    items = [CategoryOut.model_validate(c).model_dump() for c in db.scalars(select(Category).order_by(Category.name))]
    cache_set(CACHE_KEY, items, ttl=300)
    return items

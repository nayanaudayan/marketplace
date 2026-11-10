"""What the product listings actually contain: which spec fields exist, their type, range and known values.

The AI search is grounded in this, so the LLM/rules can only ask for fields that real listings have, and hard
requirements are checked against real values. Seller-supplied keys/values are untrusted text that ends up in LLM
prompts, so only simple identifiers and short plain values are admitted.
"""
import re
import time
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
VALUE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._+/-]{0,29}$")
MAX_CATEGORICAL_VALUES = 6

ACRONYMS = {"ram", "ssd", "hdd", "cpu", "gpu", "usb", "anc", "os", "hd", "tv"}
UNIT_LABELS = {"gb": "GB", "kg": "kg", "hours": "h", "mah": "mAh", "l": "L", "w": "W", "mp": "MP", "hz": "Hz"}
PREFERENCE_LABELS = {
    ("weight_kg", "asc"): "Lighter weight",
    ("battery_hours", "desc"): "Longer battery life",
    ("battery_mah", "desc"): "Bigger battery",
}


@dataclass(frozen=True)
class SpecInfo:
    key: str
    kind: str  # "number" | "boolean" | "text"
    categories: tuple[str, ...]
    minimum: float | None = None
    maximum: float | None = None
    values: tuple[str, ...] = ()  # only for low-cardinality text fields

    @property
    def unit_suffix(self) -> str | None:
        suffix = self.key.rsplit("_", 1)[-1]
        return suffix if "_" in self.key and suffix in UNIT_LABELS else None


Catalog = dict[str, SpecInfo]

_SQL = text(
    """
    SELECT e.key AS key,
           jsonb_typeof(e.value) AS kind,
           array_agg(DISTINCT c.name) AS cats,
           min(CASE WHEN jsonb_typeof(e.value) = 'number' THEN (e.value #>> '{}')::numeric END) AS lo,
           max(CASE WHEN jsonb_typeof(e.value) = 'number' THEN (e.value #>> '{}')::numeric END) AS hi,
           array_agg(DISTINCT e.value #>> '{}') FILTER (WHERE jsonb_typeof(e.value) = 'string') AS vals
    FROM products p
    JOIN categories c ON c.id = p.category_id,
         jsonb_each(p.specifications) AS e
    WHERE p.status = 'active'
    GROUP BY e.key, jsonb_typeof(e.value)
    """
)
_PRIORITY = {"number": 0, "boolean": 1, "string": 2}
_cache: tuple[float, Catalog] | None = None


def load_spec_catalog(db: Session) -> Catalog:
    global _cache
    ttl = settings.spec_catalog_ttl_seconds
    if _cache and ttl > 0 and time.monotonic() - _cache[0] < ttl:
        return _cache[1]

    chosen: dict[str, tuple[int, SpecInfo]] = {}
    for row in db.execute(_SQL):
        if not KEY_RE.match(row.key) or row.kind not in _PRIORITY:
            continue
        kind = "text" if row.kind == "string" else row.kind
        values: tuple[str, ...] = ()
        if kind == "text":
            vals = sorted(v for v in (row.vals or []) if VALUE_RE.match(v))
            if 0 < len(vals) <= MAX_CATEGORICAL_VALUES:
                values = tuple(vals)
        info = SpecInfo(
            key=row.key,
            kind=kind,
            categories=tuple(sorted(row.cats)),
            minimum=float(row.lo) if row.lo is not None else None,
            maximum=float(row.hi) if row.hi is not None else None,
            values=values,
        )
        rank = _PRIORITY[row.kind]
        if row.key not in chosen or rank < chosen[row.key][0]:  # a key with mixed types: prefer number > bool > text
            chosen[row.key] = (rank, info)
    catalog = {k: v[1] for k, v in chosen.items()}
    _cache = (time.monotonic(), catalog)
    return catalog


def invalidate_spec_catalog() -> None:
    global _cache
    _cache = None


# ----------------------------------------------------------------------------------------------- wording


def humanize(key: str) -> str:
    parts = key.split("_")
    if len(parts) > 1 and parts[-1] in UNIT_LABELS:
        parts = parts[:-1]
    name = " ".join(p.upper() if p in ACRONYMS else p for p in parts)
    return name if name[:1].isupper() else name[:1].upper() + name[1:]


def format_value(key: str, value: float | bool | str) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        suffix = key.rsplit("_", 1)[-1] if "_" in key else ""
        unit = UNIT_LABELS.get(suffix, "")
        return f"{value:g} {unit}".strip()
    return str(value)


def describe_spec(key: str, op: str, value: float | bool | str) -> str:
    name = humanize(key)
    if isinstance(value, bool):
        return name if value else f"No {name.lower()}"
    if isinstance(value, str):
        return f"{name}: {value}"
    symbol = {">=": "≥", "<=": "≤", "==": "="}[op]
    return f"{name} {symbol} {format_value(key, value)}"


def describe_preference(key: str, direction: str) -> str:
    return PREFERENCE_LABELS.get((key, direction)) or f"{'Lower' if direction == 'asc' else 'Higher'} {humanize(key).lower()}"


def prompt_lines(catalog: Catalog) -> list[str]:
    """Compact, sanitised schema description for the extraction prompt."""
    lines = []
    for info in sorted(catalog.values(), key=lambda i: i.key):
        where = ", ".join(info.categories)
        if info.kind == "number" and info.minimum is not None:
            lines.append(f"- {info.key} (number {info.minimum:g}-{info.maximum:g}; {where})")
        elif info.kind == "boolean":
            lines.append(f"- {info.key} (boolean; {where})")
        elif info.values:
            lines.append(f"- {info.key} (text: {' | '.join(info.values)}; {where})")
    return lines

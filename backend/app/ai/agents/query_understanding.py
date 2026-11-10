"""Turns a natural-language shopper request into validated structured constraints, grounded in the real listings.

The LLM is only trusted to *propose* values. Everything is validated with Pydantic and then checked against the
catalogue (the spec fields that listings actually have): unknown fields are dropped, types are coerced, categories and
brands are resolved by the caller. If the LLM is unavailable or returns junk, a rule-based extractor produces the same
schema from the same catalogue, so search keeps working.

Two kinds of listing requirements are extracted:
  * specs        - hard constraints ("16GB RAM", "512GB SSD", "under 1.5 kg", "noise cancelling"): enforced in SQL
  * preferences  - soft wishes ("lightweight", "good battery backup"): rank products by their real spec values
"""
import logging
import re
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from app.ai.prompts import extraction
from app.ai.providers.base import LLMProvider, ProviderError
from app.ai.providers.local import STOPWORDS
from app.ai.retrieval.catalog import Catalog, SpecInfo

log = logging.getLogger(__name__)
MAX_QUERY_CHARS = 500
MAX_PRICE = Decimal("100000000")
MAX_ITEMS = 6
KEY_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"


class SpecFilter(BaseModel):
    key: str = Field(pattern=KEY_PATTERN)
    op: Literal[">=", "<=", "=="]
    value: float | bool | str

    @field_validator("value")
    @classmethod
    def _short(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v or len(v) > 30:
                raise ValueError("bad value")
        return v


class Preference(BaseModel):
    key: str = Field(pattern=KEY_PATTERN)
    direction: Literal["asc", "desc"]  # asc: lower is better (weight); desc: higher is better (battery)


def _valid_items(model, raw) -> list:
    """Keeps the well-formed entries of an LLM-supplied list instead of failing the whole extraction."""
    if not isinstance(raw, list):
        return []
    items = []
    for entry in raw[:MAX_ITEMS * 2]:
        try:
            items.append(model.model_validate(entry))
        except (ValidationError, ValueError):
            continue
    return items[:MAX_ITEMS]


class ExtractedRequirements(BaseModel):
    category: str | None = None
    brand: str | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    specs: list[SpecFilter] = Field(default_factory=list)
    preferences: list[Preference] = Field(default_factory=list)
    usage: str | None = None
    keywords: list[str] = Field(default_factory=list)
    in_stock_only: bool = False

    @field_validator("category", "brand", "usage", mode="before")
    @classmethod
    def _clean_text(cls, v):
        if v is None:
            return None
        v = str(v).strip()[:60]
        return v or None

    @field_validator("min_price", "max_price", mode="before")
    @classmethod
    def _price(cls, v):
        if v in (None, "", 0):
            return None
        try:
            d = Decimal(str(v))
        except Exception:
            return None
        return d if 0 < d <= MAX_PRICE else None

    @field_validator("specs", mode="before")
    @classmethod
    def _specs(cls, v):
        return _valid_items(SpecFilter, v)

    @field_validator("preferences", mode="before")
    @classmethod
    def _preferences(cls, v):
        return _valid_items(Preference, v)

    @field_validator("keywords", mode="before")
    @classmethod
    def _keywords(cls, v):
        if not isinstance(v, list):
            return []
        cleaned = []
        for k in v[:8]:
            k = re.sub(r"[^a-z0-9 ]", "", str(k).lower()).strip()[:40]
            if k and k not in cleaned:
                cleaned.append(k)
        return cleaned

    @model_validator(mode="after")
    def _price_order(self):
        if self.min_price and self.max_price and self.min_price > self.max_price:
            self.min_price = None
        return self


# --------------------------------------------------------------------------- grounding in real listings


def _coerce_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) < 1e12 else None  # rejects NaN / absurd values


def ground(req: ExtractedRequirements, catalog: Catalog) -> ExtractedRequirements:
    """Drops anything the listings can't support: unknown fields, impossible operators, unknown categorical values."""
    specs: list[SpecFilter] = []
    seen: set[str] = set()
    for s in req.specs:
        info = catalog.get(s.key)
        if info is None or s.key in seen:
            continue
        if info.kind == "number":
            number = _coerce_number(s.value)
            if number is None:
                continue
            specs.append(SpecFilter(key=s.key, op=s.op, value=number))
        elif info.kind == "boolean":
            text = str(s.value).strip().lower()
            if isinstance(s.value, bool):
                flag = s.value
            elif text in ("true", "yes"):
                flag = True
            elif text in ("false", "no"):
                flag = False
            else:
                continue
            specs.append(SpecFilter(key=s.key, op="==", value=flag))
        else:
            canonical = next((v for v in info.values if v.lower() == str(s.value).strip().lower()), None)
            if canonical is None:
                continue
            specs.append(SpecFilter(key=s.key, op="==", value=canonical))
        seen.add(s.key)

    preferences, pref_seen = [], set()
    for p in req.preferences:
        info = catalog.get(p.key)
        if info is not None and info.kind == "number" and p.key not in pref_seen:
            preferences.append(p)
            pref_seen.add(p.key)
    return req.model_copy(update={"specs": specs, "preferences": preferences})


# --------------------------------------------------------------------------- rule-based fallback

_MULT = {"k": 1_000, "thousand": 1_000, "l": 100_000, "lakh": 100_000, "lac": 100_000, "m": 1_000_000}
_NUM = r"(?:₹|rs\.?|inr)?\s*([\d][\d,]*(?:\.\d+)?)\s*(k|thousand|lakh|lac|l|m)?\b"
_MAX_RE = re.compile(r"(?:under|below|less than|upto|up to|within|max(?:imum)?|budget(?: of)?|not more than|<)\s*" + _NUM, re.I)
_MIN_RE = re.compile(r"(?:above|over|more than|at least|min(?:imum)?|starting from|>)\s*" + _NUM, re.I)
_BETWEEN_RE = re.compile(r"between\s*" + _NUM + r"\s*(?:and|to|-)\s*" + _NUM, re.I)
_USAGE_RE = re.compile(r"\b(?:for|suitable for|good for)\s+([a-z ]{3,30}?)(?:\b(?:with|under|below|and|,|\.)|$)", re.I)

_MAX_WORDS = r"under|below|less than|upto|up to|within|max(?:imum)?|at most|lighter than|not more than|<"
_MIN_WORDS = r"above|over|at least|more than|min(?:imum)?|starting from|>"
_PRE = rf"(?P<pre>(?:{_MAX_WORDS}|{_MIN_WORDS})\s*)?"
_NUMBER = r"(?P<num>\d+(?:\.\d+)?)"

_UNIT_RE = {
    "gb": r"(?:gb|tb)",
    "kg": r"(?:kgs?|kilos?)",
    "hours": r"(?:hours?|hrs?|h)",
    "mah": r"mah",
    "l": r"(?:litres?|liters?|l)",
    "w": r"(?:watts?|w)",
    "mp": r"mp",
    "hz": r"hz",
}
_ALIASES = {
    "ram": ["ram", "memory"],
    "storage": ["storage", "ssd", "hdd", "disk", "rom"],
    "battery": ["battery", "backup"],
    "weight": ["weight", "weighs"],
    "power": ["power", "wattage"],
    "capacity": ["capacity"],
}
_BOOL_ALIASES = {"noise_cancelling": [r"noise[ -]?cancell?ing", r"anc"]}
_LOWER_IS_BETTER = ("weight",)
_LIGHT_RE = re.compile(r"\b(?:ultra[ -]?)?(?:lightweight|light[ -]weight|light|portable|slim|compact)\b", re.I)
_BATTERY_RE = re.compile(
    r"\b(?:long|good|great|big|strong|all[ -]day)\s+battery\b|\bbattery\s+(?:backup|life)\b|\bgood\s+backup\b", re.I
)


def _amount(num: str, unit: str | None) -> Decimal:
    value = Decimal(num.replace(",", ""))
    return value * _MULT.get((unit or "").lower(), 1)


def _op_from(pre: str | None, default: str) -> str:
    if not pre:
        return default
    return "<=" if re.fullmatch(rf"(?:{_MAX_WORDS})\s*", pre, re.I) else ">="


def _aliases(info: SpecInfo) -> list[str]:
    stem = info.key.rsplit("_", 1)[0] if info.unit_suffix else info.key
    words = [w for w in stem.split("_") if w]
    found: list[str] = []
    for w in words:
        found.extend(_ALIASES.get(w, [w]))
    return list(dict.fromkeys(found))


def _specs_from_text(q: str, catalog: Catalog) -> tuple[list[SpecFilter], list[Preference], str]:
    """Extracts spec constraints/preferences using only fields that exist in the catalogue.
    Returns the matched text blanked out of the query so price parsing can't mistake '1.5 kg' for a budget."""
    specs: list[SpecFilter] = []
    preferences: list[Preference] = []
    masked = q
    lowered_specs = {s.key for s in specs}

    def blank(span: tuple[int, int]) -> None:
        nonlocal masked
        masked = masked[: span[0]] + " " * (span[1] - span[0]) + masked[span[1] :]

    def add_number(info: SpecInfo, m: re.Match) -> None:
        number = float(m.group("num"))
        unit = (m.groupdict().get("unit") or "").lower()
        if info.unit_suffix == "gb" and unit.startswith("tb"):
            number *= 1024
        default = "<=" if any(info.key.startswith(w) for w in _LOWER_IS_BETTER) else ">="
        specs.append(SpecFilter(key=info.key, op=_op_from(m.group("pre"), default), value=number))
        lowered_specs.add(info.key)
        blank(m.span())

    numeric = [i for i in catalog.values() if i.kind == "number"]

    # number + unit next to a field word: "16GB RAM", "512GB SSD", "10 hours battery", "weight under 1.5 kg"
    for info in numeric:
        words = "|".join(re.escape(a) for a in _aliases(info))
        unit = _UNIT_RE.get(info.unit_suffix or "")
        if unit:
            patterns = [
                # words between value and field must not start with a digit ("16GB RAM 512GB SSD" is two fields)
                rf"{_PRE}{_NUMBER}\s*(?P<unit>{unit})\b(?:\s+of)?(?:\s+[a-z]\w*){{0,2}}?\s+(?:{words})\b",
                # the unit is mandatory here, otherwise "backup under 70,000" would read the price as a battery limit
                rf"\b(?:{words})\b\s*(?:of|is|:|=)?\s*{_PRE}{_NUMBER}\s*(?P<unit>{unit})\b",
            ]
        else:
            patterns = [rf"\b(?:{words})\b\s*(?:of|is|:|=)?\s*{_PRE}{_NUMBER}\b"]
        for pattern in patterns:
            if info.key in lowered_specs:
                break
            if m := re.search(pattern, masked, re.I):
                add_number(info, m)

    # a bare number+unit ("6000 mAh", "under 1.4 kg") when exactly one field in the catalogue uses that unit
    by_unit: dict[str, list[SpecInfo]] = {}
    for info in numeric:
        if info.unit_suffix:
            by_unit.setdefault(info.unit_suffix, []).append(info)
    for suffix, infos in by_unit.items():
        if len(infos) == 1 and infos[0].key not in lowered_specs and suffix in _UNIT_RE:
            if m := re.search(rf"{_PRE}{_NUMBER}\s*(?P<unit>{_UNIT_RE[suffix]})\b", masked, re.I):
                add_number(infos[0], m)

    for info in catalog.values():
        if info.kind == "boolean":
            phrases = [re.escape(info.key).replace("_", "[ -]")] + _BOOL_ALIASES.get(info.key, [])
            m = re.search(rf"\b(?P<neg>(?:without|no|non)[ -])?(?:{'|'.join(phrases)})\b", masked, re.I)
            if m:
                specs.append(SpecFilter(key=info.key, op="==", value=not m.group("neg")))
                blank(m.span())
        elif info.kind == "text" and info.values:
            for value in info.values:
                spaced = "[ -]".join(re.escape(part) for part in value.split("-"))  # "over-ear" also matches "over ear"
                m = re.search(rf"\b{spaced}\b", masked, re.I)
                if m:
                    specs.append(SpecFilter(key=info.key, op="==", value=value))
                    blank(m.span())
                    break

    if _LIGHT_RE.search(q) and "weight_kg" in catalog:
        preferences.append(Preference(key="weight_kg", direction="asc"))
    if _BATTERY_RE.search(q):
        preferences.extend(Preference(key=k, direction="desc") for k in ("battery_hours", "battery_mah") if k in catalog)
    return specs[:MAX_ITEMS], preferences[:MAX_ITEMS], masked


def heuristic_extract(query: str, categories: list[str], brands: list[str], catalog: Catalog | None = None) -> ExtractedRequirements:
    q = query[:MAX_QUERY_CHARS]
    catalog = catalog or {}
    data: dict = {}
    specs, preferences, price_text = _specs_from_text(q, catalog)
    data["specs"], data["preferences"] = specs, preferences

    if m := _BETWEEN_RE.search(price_text):
        data["min_price"], data["max_price"] = _amount(m.group(1), m.group(2)), _amount(m.group(3), m.group(4))
    else:
        if m := _MAX_RE.search(price_text):
            data["max_price"] = _amount(m.group(1), m.group(2))
        if m := _MIN_RE.search(price_text):
            data["min_price"] = _amount(m.group(1), m.group(2))

    lowered = q.lower()
    tokens = [t.rstrip("s") for t in re.findall(r"[a-z]{5,}", lowered)]
    for name in categories:
        singular = name.lower().rstrip("s")
        # exact word ("laptops") or a compound-word tail ("phone" -> "smartphones")
        if re.search(rf"\b{re.escape(singular)}s?\b", lowered) or any(singular.endswith(t) for t in tokens):
            data["category"] = name
            break
    for name in brands:
        if re.search(rf"\b{re.escape(name.lower())}\b", lowered):
            data["brand"] = name
            break
    if m := _USAGE_RE.search(q):
        data["usage"] = m.group(1).strip()
    data["in_stock_only"] = bool(re.search(r"in stock|available", lowered))

    stripped = re.sub(r"[\d,.]+\s*(?:gb|tb|kg|k|lakh|l)?\b", " ", price_text.lower())
    words = [w for w in re.findall(r"[a-z]{3,}", stripped) if w not in STOPWORDS | _FILLER]
    data["keywords"] = list(dict.fromkeys(words))[:8]
    return ExtractedRequirements.model_validate(data)


_FILLER = {
    "under", "below", "above", "over", "than", "less", "more", "budget", "show", "find", "looking", "between",
    "only", "ram", "memory", "that", "have", "has", "can", "give", "get", "least", "most", "weight",
}


# --------------------------------------------------------------------------- orchestration


def extract_requirements(
    llm: LLMProvider,
    query: str,
    categories: list[str],
    brands: list[str],
    catalog: Catalog,
    previous: dict | None = None,
) -> ExtractedRequirements:
    query = query.strip()[:MAX_QUERY_CHARS]
    try:
        raw = llm.generate_json(extraction.SYSTEM, extraction.build_prompt(query, categories, brands, catalog, previous))
        # null (or missing) means "not stated": use the field default instead of failing validation on it
        req = ExtractedRequirements.model_validate({k: raw[k] for k in ExtractedRequirements.model_fields if raw.get(k) is not None})
    except (ProviderError, ValidationError, AttributeError) as exc:
        log.warning("LLM extraction unavailable (%s); using rule-based extractor", exc)
        req = heuristic_extract(query, categories, brands, catalog)
    return ground(req, catalog)


def merge_context(previous: dict | None, new: ExtractedRequirements) -> ExtractedRequirements:
    """Applies a follow-up on top of earlier constraints: new values win, unspecified ones are kept.
    Specs/preferences merge per field. Switching category starts a fresh topic."""
    if not previous:
        return new
    base = ExtractedRequirements.model_validate(previous)
    fields = new.model_dump(exclude_defaults=True)
    if "category" in fields and base.category and fields["category"].lower() != base.category.lower():
        base = base.model_copy(update={"brand": None, "usage": None, "keywords": [], "specs": [], "preferences": []})
    merged = base.model_dump()
    for key, value in fields.items():
        if key == "keywords":
            merged[key] = list(dict.fromkeys([*merged.get(key, []), *value]))[:8]
        elif key in ("specs", "preferences"):
            id_field = "key"
            kept = [e for e in merged.get(key, []) if e[id_field] not in {n[id_field] for n in value}]
            merged[key] = (kept + value)[:MAX_ITEMS]
        else:
            merged[key] = value
    return ExtractedRequirements.model_validate(merged)

from __future__ import annotations

import re
from dataclasses import dataclass

_MODEL_PATTERNS = (
    re.compile(r"\b(iphone\s+(?:\d{1,2}|se)\s*(?:pro\s*max|pro|max|plus)?)\b", re.I),
    re.compile(r"\b(macbook\s+(?:air|pro)?\s*(?:m\d(?:\s*(?:pro|max|ultra))?|\d{4})?)\b", re.I),
    re.compile(r"\b(rtx\s*\d{3,4}(?:\s*(?:ti|super))?)\b", re.I),
    re.compile(r"\b(galaxy\s+s\d{1,3}\s*(?:ultra|plus)?)\b", re.I),
    re.compile(r"\b(playstation\s*[45])\b", re.I),
    re.compile(r"\b(xbox\s+(?:series\s+)?[sx])\b", re.I),
)

_STORAGE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(tb|gb|гб|тб)\b", re.I)
_MEMORY = re.compile(r"\b(\d+)\s*(gb|гб)\s*(?:ram|озу)?\b", re.I)


@dataclass(frozen=True)
class ListingAttributes:
    model: str | None
    storage_gb: float | None
    memory_gb: float | None
    condition: str
    repair_signal: bool
    completeness_signal: str
    tokens: tuple[str, ...]


def extract_attributes(title: str, description: str = "") -> ListingAttributes:
    text = " ".join(x for x in (title, description) if x).casefold()
    model = None
    for pattern in _MODEL_PATTERNS:
        match = pattern.search(text)
        if match:
            model = re.sub(r"\s+", " ", match.group(1)).strip()
            break

    storage = None
    match = _STORAGE.search(text)
    if match:
        value = float(match.group(1))
        unit = match.group(2).casefold()
        storage = value * 1024 if unit in {"tb", "тб"} else value

    memory = None
    match = _MEMORY.search(text)
    if match:
        memory = float(match.group(1))

    repair = any(x in text for x in ("после ремонта", "ремонт", "замен", "восстанов"))
    missing = any(x in text for x in ("без короб", "без заряд", "без комплект", "только телефон", "только пристав"))
    complete = "incomplete" if missing else "complete" if any(x in text for x in ("полный комплект", "комплект", "гарантия")) else "unknown"
    if any(x in text for x in ("новый", "новая", "запечатан")):
        condition = "new"
    elif any(x in text for x in ("идеал", "отличное", "отличном", "как новый")):
        condition = "excellent"
    elif any(x in text for x in ("хорошее", "хорошем")):
        condition = "good"
    elif any(x in text for x in ("трещин", "разбит", "неисправ", "на запчасти")):
        condition = "damaged"
    else:
        condition = "unknown"

    tokens = tuple(sorted(set(re.findall(r"[\w]{3,}", text))))
    return ListingAttributes(model, storage, memory, condition, repair, complete, tokens)

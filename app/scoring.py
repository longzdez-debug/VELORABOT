from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class DealScore:
    score: int
    market_price: float | None
    deviation_pct: float | None
    estimated_profit: float | None
    liquidity: int
    risk: int
    reasons: list[str]


_NEGATIVE = (
    "не работает", "неисправ", "на запчасти", "разбит", "трещин",
    "трещина", "залит", "после ремонта", "ремонт", "дефект", "не полный",
)
_POSITIVE = (
    "идеал", "новый", "гарантия", "комплект", "полный комплект",
    "без ремонта", "без ремонтов", "отличное состояние", "отличное",
)
_MISSING = ("только", "без заряд", "без короб", "нет короб", "без комплект")


def _robust_market(prices: list[float]) -> float:
    prices = sorted(p for p in prices if p > 0)
    if not prices:
        return 0.0
    # Median is deliberately used instead of the mean: outliers must not move
    # the reference price for a reseller decision.
    return prices[len(prices) // 2]


def _risk(description: str) -> tuple[int, list[str]]:
    text = re.sub(r"\s+", " ", description.casefold())
    risk = 20
    reasons: list[str] = []
    negatives = [x for x in _NEGATIVE if x in text]
    positives = [x for x in _POSITIVE if x in text]
    missing = [x for x in _MISSING if x in text]
    if negatives:
        risk += min(45, 15 + 8 * len(set(negatives)))
        reasons.append("В описании обнаружены признаки состояния/ремонта, требующие проверки")
    if missing:
        risk += min(20, 7 * len(set(missing)))
        reasons.append("Описание указывает на неполный комплект или отсутствующие элементы")
    if positives:
        risk -= min(12, 4 * len(set(positives)))
        reasons.append("В описании есть позитивные сигналы состояния/комплектации")
    risk = max(0, min(100, risk))
    return risk, reasons


def calculate_deal_score(
    price: float,
    comparable_prices: list[float],
    description: str = "",
    *,
    comparable_count: int | None = None,
) -> DealScore:
    prices = sorted(p for p in comparable_prices if p > 0)
    if not prices or price <= 0:
        return DealScore(0, None, None, None, 0, 70, ["Недостаточно рыночных наблюдений"])

    market = _robust_market(prices)
    deviation = (market - price) / market * 100 if market else 0.0
    count = comparable_count if comparable_count is not None else len(prices)

    # Liquidity here is an evidence score, not a claim that the item will sell.
    liquidity = min(95, 25 + count * 4)
    risk, reasons = _risk(description)

    if deviation >= 25:
        reasons.insert(0, "Цена существенно ниже наблюдаемой медианы рынка")
    elif deviation >= 15:
        reasons.insert(0, "Цена заметно ниже наблюдаемой медианы рынка")
    elif deviation >= 7:
        reasons.insert(0, "Цена ниже наблюдаемой медианы рынка")
    else:
        reasons.insert(0, "Ценовое преимущество ограничено")

    advantage = max(0.0, min(65.0, deviation * 1.9))
    evidence = min(15.0, count * 0.5)
    score = round(max(0.0, min(100.0, advantage + liquidity * 0.18 + (100 - risk) * 0.17 + evidence)))
    profit = max(0.0, market - price)
    return DealScore(score, market, deviation, profit, liquidity, risk, reasons)

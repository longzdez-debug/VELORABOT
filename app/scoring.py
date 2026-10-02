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
    sale_lt_24h_pct: float | None = None
    sale_lt_3d_pct: float | None = None
    sale_lt_7d_pct: float | None = None


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


def liquidity_estimates(liquidity: int, observed_days: float = 0.0) -> tuple[float, float, float]:
    # Evidence-based heuristic until VELORA has enough resolved sale outcomes.
    # It is intentionally labeled as an estimate, never a guarantee.
    age_factor = max(0.55, 1.0 - min(max(observed_days, 0.0), 30.0) / 60.0)
    base = min(92.0, 18.0 + liquidity * 0.72) * age_factor
    p24 = max(1.0, min(95.0, base * 0.45))
    p3d = max(p24, min(97.0, base * 0.78))
    p7d = max(p3d, min(99.0, base))
    return round(p24, 1), round(p3d, 1), round(p7d, 1)


def calculate_deal_score(
    price: float,
    comparable_prices: list[float],
    description: str = "",
    *,
    comparable_count: int | None = None,
    observed_days: float = 0.0,
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
    p24, p3d, p7d = liquidity_estimates(liquidity, observed_days)
    return DealScore(score, market, deviation, profit, liquidity, risk, reasons, p24, p3d, p7d)

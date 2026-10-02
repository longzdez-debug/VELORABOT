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

def calculate_deal_score(price: float, comparable_prices: list[float], description: str = "") -> DealScore:
    prices = sorted(p for p in comparable_prices if p > 0)
    if not prices:
        return DealScore(0, None, None, None, 0, 70, ["Недостаточно рыночных наблюдений"])
    market = prices[len(prices) // 2]
    deviation = (market - price) / market * 100 if market else 0.0
    liquidity = min(95, 35 + len(prices) * 5)
    risk = 35
    reasons = []
    if deviation >= 20: reasons.append("Цена заметно ниже медианы рынка")
    elif deviation >= 10: reasons.append("Цена ниже медианы рынка")
    else: reasons.append("Ценовое преимущество ограничено")
    text = description.lower()
    if any(x in text for x in ("не работает", "на запчасти", "разбит", "трещин")):
        risk += 25; reasons.append("Описание содержит потенциальный риск")
    if any(x in text for x in ("идеал", "новый", "гарантия", "комплект")):
        risk -= 10; reasons.append("Описание содержит позитивные сигналы")
    risk = max(0, min(100, risk))
    advantage = max(0, min(60, deviation * 1.8))
    score = round(max(0, min(100, advantage + liquidity * .25 + (100 - risk) * .15)))
    return DealScore(score, market, deviation, max(0.0, market - price), liquidity, risk, reasons)

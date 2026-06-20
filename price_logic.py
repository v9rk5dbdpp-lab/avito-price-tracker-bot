from statistics import median

def fair_price(prices: list[int], min_items: int = 5) -> int | None:
    clean = sorted(p for p in prices if p and p > 0)
    if len(clean) < min_items:
        return None
    if len(clean) >= 10:
        cut = max(1, int(len(clean) * 0.1))
        clean = clean[cut:-cut]
    return int(median(clean)) if clean else None

def discount_percent(price: int, base_price: int) -> float:
    if base_price <= 0:
        return 0.0
    return round((base_price - price) / base_price * 100, 1)

def is_good_deal(price: int, base_price: int, threshold_percent: int) -> bool:
    return discount_percent(price, base_price) >= threshold_percent

from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class MarketItem:
    source: str
    external_id: str
    title: str
    price: int
    url: str
    location: str | None = None
    seller: str | None = None
    published_at: str | None = None
    found_at: str = datetime.utcnow().isoformat(timespec="seconds")

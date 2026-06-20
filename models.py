from dataclasses import dataclass, field
from datetime import datetime


def utc_now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


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
    found_at: str = field(default_factory=utc_now_iso)

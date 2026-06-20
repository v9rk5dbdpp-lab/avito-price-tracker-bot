from models import MarketItem
from sources.base import SourceClient

class WildberriesClient(SourceClient):
    source_name = "wildberries"

    async def search(self, query: str, limit: int = 30) -> list[MarketItem]:
        # Заглушка. У WB удобнее идти через их публичные JSON-ответы поиска.
        return []

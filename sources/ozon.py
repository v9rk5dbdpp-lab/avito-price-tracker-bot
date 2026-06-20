from models import MarketItem
from sources.base import SourceClient

class OzonClient(SourceClient):
    source_name = "ozon"

    async def search(self, query: str, limit: int = 30) -> list[MarketItem]:
        # Заглушка. Подключим вторым этапом после проверки ядра на Авито.
        return []

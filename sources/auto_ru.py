from models import MarketItem
from sources.base import SourceClient

class AutoRuClient(SourceClient):
    source_name = "auto_ru"

    async def search(self, query: str, limit: int = 30) -> list[MarketItem]:
        # Заглушка. Для авто лучше отдельно хранить марку, модель, год, пробег.
        return []

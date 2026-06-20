from abc import ABC, abstractmethod
from models import MarketItem

class SourceClient(ABC):
    source_name: str

    @abstractmethod
    async def search(self, query: str, limit: int = 30) -> list[MarketItem]:
        raise NotImplementedError

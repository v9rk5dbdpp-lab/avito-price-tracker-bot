from sources.avito import AvitoClient
from sources.ozon import OzonClient
from sources.wildberries import WildberriesClient
from sources.auto_ru import AutoRuClient

CLIENTS = {
    "avito": AvitoClient(),
    "ozon": OzonClient(),
    "wildberries": WildberriesClient(),
    "auto_ru": AutoRuClient(),
}

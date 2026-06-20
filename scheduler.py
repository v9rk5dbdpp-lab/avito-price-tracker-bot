import logging
from aiogram import Bot
from database import all_watches, save_item, get_prices, was_alert_sent, mark_alert_sent
from price_logic import fair_price, discount_percent, is_good_deal
from sources import CLIENTS

log = logging.getLogger(__name__)

async def check_all_watches(bot: Bot, config: dict) -> None:
    radar_cfg = config["radar"]
    watches = await all_watches()
    for watch_id, chat_id, source, query, threshold_percent in watches:
        sources = list(CLIENTS.keys()) if source == "all" else [source]
        for source_name in sources:
            client = CLIENTS.get(source_name)
            if not client:
                continue
            try:
                found = await client.search(query, limit=radar_cfg["max_items_per_check"])
            except Exception as e:
                log.exception("Source %s failed for %s: %s", source_name, query, e)
                continue

            for item in found:
                is_new = await save_item(watch_id, item)
                if not is_new:
                    continue

                prices = await get_prices(watch_id, radar_cfg["history_days_for_average"])
                base = fair_price(prices, radar_cfg["min_items_for_average"])
                if base is None:
                    continue

                if await was_alert_sent(watch_id, item.external_id):
                    continue

                if is_good_deal(item.price, base, threshold_percent):
                    diff = discount_percent(item.price, base)
                    text = (
                        f"🔥 Найден товар дешевле рынка\n\n"
                        f"Источник: {item.source}\n"
                        f"Запрос: {query}\n"
                        f"Название: {item.title}\n"
                        f"Цена: {item.price:,} ₽\n".replace(",", " ") +
                        f"Типичная цена: {base:,} ₽\n".replace(",", " ") +
                        f"Выгода: {diff}%\n\n"
                        f"{item.url}"
                    )
                    await bot.send_message(chat_id, text)
                    await mark_alert_sent(watch_id, item.external_id)

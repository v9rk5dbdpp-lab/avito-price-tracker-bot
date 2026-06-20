import asyncio
import logging
import os
import yaml
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from database import init_db, set_db_path, add_watch, list_watches, delete_watch
from scheduler import check_all_watches

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

TOKEN = os.getenv("BOT_TOKEN") or config["telegram"]["bot_token"]
if not TOKEN or TOKEN == "PUT_YOUR_TOKEN_HERE":
    raise RuntimeError("Укажи BOT_TOKEN в переменной окружения или в config.yaml")

set_db_path(config["database"]["path"])
bot = Bot(token=TOKEN)
dp = Dispatcher()

HELP = """
📡 Price Radar

Команды:
/start — меню
/add avito iPhone 15 Pro 256GB — следить за Авито
/add all iPhone 15 Pro 256GB — искать везде
/list — мои правила
/delete 3 — удалить правило
/check — проверить прямо сейчас

Источники: avito, ozon, wildberries, auto_ru, all
""".strip()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(HELP)

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Пример: /add avito iPhone 15 Pro 256GB")
        return
    source = parts[1].lower().strip()
    query = parts[2].strip()
    allowed = {"avito", "ozon", "wildberries", "auto_ru", "all"}
    if source not in allowed:
        await message.answer("Источник должен быть: avito, ozon, wildberries, auto_ru или all")
        return
    threshold = int(config["radar"]["discount_threshold_percent"])
    watch_id = await add_watch(message.chat.id, source, query, threshold)
    await message.answer(f"✅ Правило #{watch_id} добавлено\nИсточник: {source}\nЗапрос: {query}\nПорог: −{threshold}%")

@dp.message(Command("list"))
async def cmd_list(message: types.Message):
    rows = await list_watches(message.chat.id)
    if not rows:
        await message.answer("Пока правил нет. Добавь первое: /add avito iPhone 15 Pro 256GB")
        return
    text = "📋 Твои правила:\n\n" + "\n".join(
        f"#{watch_id} · {source} · {query} · −{threshold}%"
        for watch_id, source, query, threshold, _ in rows
    )
    await message.answer(text)

@dp.message(Command("delete"))
async def cmd_delete(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Пример: /delete 3")
        return
    ok = await delete_watch(message.chat.id, int(parts[1]))
    await message.answer("Удалено ✅" if ok else "Не нашел такое правило")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    await message.answer("Запускаю проверку. Если найду сделку ниже рынка, пришлю отдельно.")
    await check_all_watches(bot, config)
    await message.answer("Проверка завершена.")

async def main():
    await init_db()
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")
    scheduler.add_job(
        check_all_watches,
        "interval",
        minutes=int(config["radar"]["check_interval_minutes"]),
        args=[bot, config],
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    log.info("Price Radar started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import logging
import os
import yaml
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
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

# Простое временное хранилище выбора пользователя.
# Для MVP достаточно памяти процесса. Позже перенесем в БД или FSM-хранилище aiogram.
USER_DRAFTS: dict[int, dict[str, str]] = {}

IPHONE_GENERATIONS = ["14", "15", "16", "17", "18"]
IPHONE_VARIANTS = [
    ("Обычный", ""),
    ("Plus", "Plus"),
    ("Pro", "Pro"),
    ("Pro Max", "Pro Max"),
]
IPHONE_STORAGES = ["128GB", "256GB", "512GB", "1TB"]

HELP = """
📡 Price Radar

Команды:
/start — меню
/add avito iPhone 15 Pro 256GB — следить за Авито вручную
/add all iPhone 15 Pro 256GB — искать везде вручную
/list — мои правила
/delete 3 — удалить правило
/check — проверить прямо сейчас

Можно просто написать: iPhone или айфон.
Бот откроет меню выбора модели кнопками.

Источники: avito, ozon, wildberries, auto_ru, all
""".strip()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить позицию", callback_data="add_position")],
            [InlineKeyboardButton(text="📋 Мои правила", callback_data="show_watches")],
            [InlineKeyboardButton(text="🔎 Проверить сейчас", callback_data="run_check")],
        ]
    )


def iphone_generation_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"iPhone {gen}", callback_data=f"iphone:gen:{gen}")]
        for gen in IPHONE_GENERATIONS
    ]
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def iphone_variant_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"iphone:variant:{value or 'base'}")]
        for title, value in IPHONE_VARIANTS
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="iphone:back:gen")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def iphone_storage_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=storage, callback_data=f"iphone:storage:{storage}")]
        for storage in IPHONE_STORAGES
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="iphone:back:variant")])
    rows.append([InlineKeyboardButton(text="❌ Отмена", callback_data="wizard:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Добавить", callback_data="iphone:confirm")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="wizard:cancel")],
        ]
    )


def build_iphone_query(draft: dict[str, str]) -> str:
    generation = draft["generation"]
    variant = draft.get("variant", "")
    storage = draft["storage"]
    parts = ["iPhone", generation]
    if variant:
        parts.append(variant)
    parts.append(storage)
    return " ".join(parts)


def looks_like_iphone(text: str) -> bool:
    normalized = text.lower().replace("ё", "е")
    return "iphone" in normalized or "айфон" in normalized


async def show_watches(message: types.Message, chat_id: int) -> None:
    rows = await list_watches(chat_id)
    if not rows:
        await message.answer("Пока правил нет. Нажми “Добавить позицию” или напиши iPhone.", reply_markup=main_menu())
        return
    text = "📋 Твои правила:\n\n" + "\n".join(
        f"#{watch_id} · {source} · {query} · −{threshold}%"
        for watch_id, source, query, threshold, _ in rows
    )
    await message.answer(text, reply_markup=main_menu())


async def start_iphone_wizard(message: types.Message, user_id: int) -> None:
    USER_DRAFTS[user_id] = {
        "category": "phone",
        "brand": "Apple",
        "family": "iPhone",
        "source": "avito",
    }
    await message.answer("Выберите поколение iPhone:", reply_markup=iphone_generation_keyboard())


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(HELP, reply_markup=main_menu())


@dp.callback_query(F.data == "add_position")
async def cb_add_position(callback: types.CallbackQuery):
    await callback.message.answer("Введите название товара для поиска и анализа цен. Например: iPhone")
    await callback.answer()


@dp.callback_query(F.data == "show_watches")
async def cb_show_watches(callback: types.CallbackQuery):
    await show_watches(callback.message, callback.message.chat.id)
    await callback.answer()


@dp.callback_query(F.data == "run_check")
async def cb_run_check(callback: types.CallbackQuery):
    await callback.message.answer("Запускаю проверку. Если найду сделку ниже рынка, пришлю отдельно.")
    await check_all_watches(bot, config)
    await callback.message.answer("Проверка завершена.")
    await callback.answer()


@dp.callback_query(F.data == "wizard:cancel")
async def cb_cancel(callback: types.CallbackQuery):
    USER_DRAFTS.pop(callback.from_user.id, None)
    await callback.message.edit_text("Добавление позиции отменено.")
    await callback.answer()


@dp.callback_query(F.data.startswith("iphone:gen:"))
async def cb_iphone_generation(callback: types.CallbackQuery):
    generation = callback.data.split(":")[-1]
    draft = USER_DRAFTS.setdefault(callback.from_user.id, {})
    draft.update({
        "category": "phone",
        "brand": "Apple",
        "family": "iPhone",
        "source": "avito",
        "generation": generation,
    })
    await callback.message.edit_text(
        f"Вы выбрали iPhone {generation}.\nТеперь выберите модель:",
        reply_markup=iphone_variant_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("iphone:variant:"))
async def cb_iphone_variant(callback: types.CallbackQuery):
    raw_variant = callback.data.split(":")[-1]
    variant = "" if raw_variant == "base" else raw_variant
    draft = USER_DRAFTS.setdefault(callback.from_user.id, {})
    draft["variant"] = variant
    generation = draft.get("generation", "")
    title = f"iPhone {generation} {variant}".strip()
    await callback.message.edit_text(
        f"Вы выбрали {title}.\nТеперь выберите объём памяти:",
        reply_markup=iphone_storage_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data.startswith("iphone:storage:"))
async def cb_iphone_storage(callback: types.CallbackQuery):
    storage = callback.data.split(":")[-1]
    draft = USER_DRAFTS.setdefault(callback.from_user.id, {})
    draft["storage"] = storage
    query = build_iphone_query(draft)
    await callback.message.edit_text(
        f"Проверьте позицию:\n\n📱 {query}\nИсточник: Avito\nПорог: −{int(config['radar']['discount_threshold_percent'])}%",
        reply_markup=confirm_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "iphone:back:gen")
async def cb_iphone_back_gen(callback: types.CallbackQuery):
    await callback.message.edit_text("Выберите поколение iPhone:", reply_markup=iphone_generation_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "iphone:back:variant")
async def cb_iphone_back_variant(callback: types.CallbackQuery):
    generation = USER_DRAFTS.get(callback.from_user.id, {}).get("generation", "")
    await callback.message.edit_text(
        f"Вы выбрали iPhone {generation}.\nТеперь выберите модель:",
        reply_markup=iphone_variant_keyboard(),
    )
    await callback.answer()


@dp.callback_query(F.data == "iphone:confirm")
async def cb_iphone_confirm(callback: types.CallbackQuery):
    draft = USER_DRAFTS.get(callback.from_user.id)
    if not draft or "generation" not in draft or "storage" not in draft:
        await callback.message.edit_text("Не хватает данных для добавления позиции. Начните заново: напишите iPhone.")
        await callback.answer()
        return

    query = build_iphone_query(draft)
    source = draft.get("source", "avito")
    threshold = int(config["radar"]["discount_threshold_percent"])
    watch_id = await add_watch(callback.message.chat.id, source, query, threshold)
    USER_DRAFTS.pop(callback.from_user.id, None)

    await callback.message.edit_text(
        f"✅ Правило #{watch_id} добавлено\n\n"
        f"Товар: {query}\n"
        f"Источник: {source}\n"
        f"Порог: −{threshold}%"
    )
    await callback.answer()


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
    await show_watches(message, message.chat.id)


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


@dp.message(F.text)
async def smart_text_entry(message: types.Message):
    text = message.text.strip()
    if looks_like_iphone(text):
        await start_iphone_wizard(message, message.from_user.id)
        return

    await message.answer(
        "Пока я умею автоматически распознавать iPhone.\n"
        "Напиши iPhone или используй ручную команду:\n"
        "/add avito название товара",
        reply_markup=main_menu(),
    )


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

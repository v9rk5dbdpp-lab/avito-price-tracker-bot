import aiosqlite
from datetime import datetime, timedelta
from models import MarketItem

DB_PATH = "price_radar.db"


def set_db_path(path: str) -> None:
    global DB_PATH
    DB_PATH = path


def normalize_query(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS watches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                query TEXT NOT NULL,
                threshold_percent INTEGER NOT NULL DEFAULT 20,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                external_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                url TEXT NOT NULL,
                location TEXT,
                seller TEXT,
                published_at TEXT,
                found_at TEXT NOT NULL,
                UNIQUE(source, external_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                watch_id INTEGER NOT NULL,
                item_external_id TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                UNIQUE(watch_id, item_external_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS search_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                raw_query TEXT NOT NULL,
                normalized_query TEXT NOT NULL,
                recognized_template TEXT,
                created_at TEXT NOT NULL
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_search_stats_normalized_query ON search_stats(normalized_query)"
        )
        await db.commit()


async def record_search_query(chat_id: int, raw_query: str, recognized_template: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO search_stats(chat_id, raw_query, normalized_query, recognized_template, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                raw_query.strip(),
                normalize_query(raw_query),
                recognized_template,
                datetime.utcnow().isoformat(timespec="seconds"),
            ),
        )
        await db.commit()


async def top_search_queries(limit: int = 10, days: int = 30) -> list[tuple[str, int]]:
    since = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            """
            SELECT normalized_query, COUNT(*) AS total
            FROM search_stats
            WHERE created_at >= ?
            GROUP BY normalized_query
            ORDER BY total DESC, normalized_query ASC
            LIMIT ?
            """,
            (since, limit),
        )
        return [(str(row[0]), int(row[1])) for row in await cur.fetchall()]


async def add_watch(chat_id: int, source: str, query: str, threshold_percent: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO watches(chat_id, source, query, threshold_percent, created_at) VALUES (?, ?, ?, ?, ?)",
            (chat_id, source, query, threshold_percent, datetime.utcnow().isoformat(timespec="seconds")),
        )
        await db.commit()
        return int(cur.lastrowid)


async def list_watches(chat_id: int) -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT id, source, query, threshold_percent, created_at FROM watches WHERE chat_id=? ORDER BY id DESC",
            (chat_id,),
        )
        return await cur.fetchall()


async def delete_watch(chat_id: int, watch_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("DELETE FROM watches WHERE id=? AND chat_id=?", (watch_id, chat_id))
        await db.commit()
        return cur.rowcount > 0


async def all_watches() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT id, chat_id, source, query, threshold_percent FROM watches ORDER BY id")
        return await cur.fetchall()


async def save_item(watch_id: int, item: MarketItem) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute(
                """
                INSERT INTO items(watch_id, source, external_id, title, price, url, location, seller, published_at, found_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (watch_id, item.source, item.external_id, item.title, item.price, item.url,
                 item.location, item.seller, item.published_at, item.found_at),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False


async def get_prices(watch_id: int, days: int) -> list[int]:
    since = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT price FROM items WHERE watch_id=? AND found_at>=? AND price>0",
            (watch_id, since),
        )
        return [int(row[0]) for row in await cur.fetchall()]


async def was_alert_sent(watch_id: int, external_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM alerts WHERE watch_id=? AND item_external_id=? LIMIT 1",
            (watch_id, external_id),
        )
        return await cur.fetchone() is not None


async def mark_alert_sent(watch_id: int, external_id: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO alerts(watch_id, item_external_id, sent_at) VALUES (?, ?, ?)",
            (watch_id, external_id, datetime.utcnow().isoformat(timespec="seconds")),
        )
        await db.commit()

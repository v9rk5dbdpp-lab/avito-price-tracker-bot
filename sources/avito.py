import re
from urllib.parse import quote_plus, urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from models import MarketItem
from sources.base import SourceClient

class AvitoClient(SourceClient):
    source_name = "avito"

    async def search(self, query: str, limit: int = 30) -> list[MarketItem]:
        url = f"https://www.avito.ru/all?q={quote_plus(query)}"
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page(locale="ru-RU")
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(2500)
            html = await page.content()
            await browser.close()
        return self._parse_html(html, limit)

    def _parse_html(self, html: str, limit: int) -> list[MarketItem]:
        soup = BeautifulSoup(html, "html.parser")
        items: list[MarketItem] = []
        seen: set[str] = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            text = " ".join(a.get_text(" ", strip=True).split())
            if not text or "₽" not in text:
                continue

            price_match = re.search(r"([0-9][0-9\s]{2,})\s*₽", text)
            if not price_match:
                continue

            price = int(re.sub(r"\D", "", price_match.group(1)))
            title = text[: price_match.start()].strip(" -–—•") or text[:120]
            full_url = urljoin("https://www.avito.ru", href.split("?")[0])
            external_id_match = re.search(r"_(\d+)$", full_url)
            external_id = external_id_match.group(1) if external_id_match else full_url

            if external_id in seen:
                continue
            seen.add(external_id)

            items.append(MarketItem(
                source=self.source_name,
                external_id=external_id,
                title=title[:200],
                price=price,
                url=full_url,
            ))
            if len(items) >= limit:
                break
        return items

import asyncio
import re
from datetime import datetime
from urllib.parse import quote
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot

from hunter_config import REFERRAL_REGEX
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

INTERVAL_NOTE = 30  # Polling note.com setiap 30 detik

SEARCH_QUERIES = [
    "claude.ai/referral",
    "claude referral",
    "claude 招待",
    "claude プロモコード",
    "claude pro 招待"
]

class NoteWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = True
        self.scanned_articles = set()

    def get_headers(self):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
        }

    async def scan_article(self, session: aiohttp.ClientSession, article_url: str):
        """Ambil konten artikel note.com dan ekstrak semua link referral."""
        if article_url in self.scanned_articles:
            return
        self.scanned_articles.add(article_url)

        try:
            async with session.get(article_url, headers=self.get_headers(), timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return

                html_text = await resp.text()
                matches = re.findall(REFERRAL_REGEX, html_text)
                if not matches:
                    return

                # Ekstrak judul dan author
                soup = BeautifulSoup(html_text, "html.parser")
                title = soup.title.string.strip() if soup.title else "note.com article"
                author_match = re.search(r"note\.(?:com|jp)/([^/]+)/n/", article_url)
                author = f"@{author_match.group(1)}" if author_match else "note_creator"

                for code in set(matches):
                    if not db.is_link_seen(code):
                        clean_url = f"https://claude.ai/referral/{code}"
                        saved = db.save_referral(
                            code=code,
                            url=clean_url,
                            source="note.com",
                            author=author,
                            raw_content=f"{title} ({article_url})"
                        )
                        if saved:
                            print(f"[HIT NOTE.COM] Ditemukan link Claude di note.com: {clean_url} oleh {author}")
                            await send_referral_alert(
                                bot=self.bot,
                                code=code,
                                url=clean_url,
                                source="note.com",
                                author=author,
                                snippet=title[:120],
                                source_url=article_url
                            )
        except Exception:
            pass

    async def scan_search(self, session: aiohttp.ClientSession, query: str):
        """Cari artikel baru di note.com berdasarkan query."""
        url = f"https://note.com/search?q={quote(query)}&context=note&mode=search"
        try:
            async with session.get(url, headers=self.get_headers(), timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return

                html_text = await resp.text()
                soup = BeautifulSoup(html_text, "html.parser")
                article_links = []
                for a in soup.find_all("a"):
                    href = a.get("href") or ""
                    if "/n/" in href:
                        if href.startswith("/"):
                            href = "https://note.com" + href
                        if "note.com/" in href or "note.jp/" in href:
                            article_links.append(href)

                # Periksa setiap artikel yang ditemukan
                for link in article_links:
                    if not self.running:
                        break
                    await self.scan_article(session, link)
                    await asyncio.sleep(0.5)
        except Exception:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] note.com Scanner aktif (Japanese Creator & Community Blog)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                for q in SEARCH_QUERIES:
                    if not self.running:
                        break
                    await self.scan_search(session, q)
                    await asyncio.sleep(2.0)

                # Batasi memory set cache maksimal 2000 URL agar tidak membengkak
                if len(self.scanned_articles) > 2000:
                    self.scanned_articles.clear()

                await asyncio.sleep(INTERVAL_NOTE)

    def stop(self):
        self.running = False

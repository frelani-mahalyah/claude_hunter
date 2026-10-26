import asyncio
import re
from datetime import datetime
import aiohttp
from telegram import Bot

from hunter_config import REFERRAL_REGEX
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

INTERVAL_WAYBACK = 60  # Polling Wayback Machine CDX API setiap 60 detik

class WaybackWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = True

    async def scan(self, session: aiohttp.ClientSession):
        """Query Wayback Machine CDX Server untuk URL claude.ai/referral/* terbaru."""
        url = "https://web.archive.org/cdx/search/cdx?url=claude.ai/referral/*&output=json&fl=original,timestamp&sort=reverse&limit=40"
        headers = {
            "User-Agent": "ClaudeHunterBot/1.0 (Mozilla/5.0 Wayback Scanner)",
            "Accept": "application/json"
        }
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=12)) as resp:
                if resp.status != 200:
                    return

                rows = await resp.json()
                if not rows or len(rows) < 2:
                    return

                # Baris 0 adalah header ['original', 'timestamp'], baris berikutnya adalah data
                for row in rows[1:]:
                    if len(row) < 2:
                        continue
                    original_url, timestamp = row[0], row[1]
                    matches = re.findall(REFERRAL_REGEX, original_url)
                    if not matches:
                        continue

                    # Parse timestamp Wayback YYYYMMDDhhmmss
                    dt_str = ""
                    try:
                        if len(timestamp) >= 14:
                            dt = datetime.strptime(timestamp[:14], "%Y%m%d%H%M%S")
                            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                    archive_view_url = f"https://web.archive.org/web/{timestamp}/{original_url}"

                    for code in set(matches):
                        if not db.is_link_seen(code):
                            clean_url = f"https://claude.ai/referral/{code}"
                            saved = db.save_referral(
                                code=code,
                                url=clean_url,
                                source="Wayback Machine",
                                author="Archive.org",
                                raw_content=f"Archived at {timestamp} ({archive_view_url})"
                            )
                            if saved:
                                print(f"[HIT WAYBACK] Ditemukan link Claude dari Wayback: {clean_url}")
                                await send_referral_alert(
                                    bot=self.bot,
                                    code=code,
                                    url=clean_url,
                                    source="Wayback Machine",
                                    author="@ArchiveOrg",
                                    snippet=f"URL terindeks di Wayback Machine ({dt_str or timestamp})",
                                    source_url=archive_view_url
                                )
        except Exception as e:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] Wayback Machine Scanner aktif (Archive.org CDX API)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                try:
                    await self.scan(session)
                except Exception as e:
                    pass
                await asyncio.sleep(INTERVAL_WAYBACK)

    def stop(self):
        self.running = False

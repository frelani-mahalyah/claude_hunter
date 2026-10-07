import asyncio
import re
from datetime import datetime
import aiohttp
from telegram import Bot

from hunter_config import INTERVAL_HACKERNEWS, REFERRAL_REGEX
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

class HackerNewsWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False

    async def scan(self, session: aiohttp.ClientSession):
        url = "http://hn.algolia.com/api/v1/search_by_date?query=claude.ai/referral&tags=(story,comment)&hitsPerPage=20"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                hits = data.get("hits", [])
                for hit in hits:
                    text = (hit.get("comment_text") or "") + " " + (hit.get("story_text") or "") + " " + (hit.get("url") or "")
                    matches = re.findall(REFERRAL_REGEX, text)
                    if not matches:
                        continue

                    author = hit.get("author", "hn_user")
                    story_id = hit.get("story_id") or hit.get("objectID")
                    hn_url = f"https://news.ycombinator.com/item?id={story_id}"

                    for code in set(matches):
                        if not db.is_link_seen(code):
                            clean_url = f"https://claude.ai/referral/{code}"
                            saved = db.save_referral(
                                code=code,
                                url=clean_url,
                                source="HackerNews",
                                author=f"u/{author}",
                                raw_content=text[:300]
                            )
                            if saved:
                                print(f"[HIT HACKERNEWS] Ditemukan link baru oleh {author}: {clean_url}")
                                await send_referral_alert(
                                    bot=self.bot,
                                    code=code,
                                    url=clean_url,
                                    source="HackerNews",
                                    author=f"u/{author}",
                                    snippet=text[:150],
                                    source_url=hn_url
                                )
        except Exception:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] HackerNews Scanner aktif (Algolia realtime)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                await self.scan(session)
                await asyncio.sleep(INTERVAL_HACKERNEWS)

    def stop(self):
        self.running = False

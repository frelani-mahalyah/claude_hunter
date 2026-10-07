import asyncio
import re
from datetime import datetime
import aiohttp
from telegram import Bot

from hunter_config import INTERVAL_GITHUB, REFERRAL_REGEX
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

class GitHubWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False

    async def scan(self, session: aiohttp.ClientSession):
        url = "https://api.github.com/search/issues?q=claude.ai/referral+is:open&sort=created&order=desc&per_page=15"
        headers = {
            "User-Agent": "ClaudeHunterBot/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return

                data = await resp.json()
                items = data.get("items", [])
                for item in items:
                    body = (item.get("body") or "") + " " + (item.get("title") or "")
                    matches = re.findall(REFERRAL_REGEX, body)
                    if not matches:
                        continue

                    user = item.get("user", {})
                    author = user.get("login", "gh_user")
                    html_url = item.get("html_url")

                    for code in set(matches):
                        if not db.is_link_seen(code):
                            clean_url = f"https://claude.ai/referral/{code}"
                            saved = db.save_referral(
                                code=code,
                                url=clean_url,
                                source="GitHub Issues",
                                author=f"@{author}",
                                raw_content=body[:300]
                            )
                            if saved:
                                print(f"[HIT GITHUB] Ditemukan link baru oleh {author}: {clean_url}")
                                await send_referral_alert(
                                    bot=self.bot,
                                    code=code,
                                    url=clean_url,
                                    source="GitHub",
                                    author=f"@{author}",
                                    snippet=body[:150],
                                    source_url=html_url
                                )
        except Exception:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] GitHub Scanner aktif (Issues & Discussions)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                await self.scan(session)
                await asyncio.sleep(INTERVAL_GITHUB)

    def stop(self):
        self.running = False

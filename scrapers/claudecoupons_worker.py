import asyncio
import re
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot

from hunter_config import REFERRAL_REGEX, INTERVAL_CLAUDECOUPONS
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

class ClaudeCouponsWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.interval = INTERVAL_CLAUDECOUPONS

    async def scan_github_repo(self, session: aiohttp.ClientSession):
        """Pantau repo GitHub Instafill/claude-coupons (Issues, PR, Commits)."""
        headers = {
            "User-Agent": "ClaudeHunterBot/1.0",
            "Accept": "application/vnd.github.v3+json"
        }

        # 1. Cek Issues & Comments
        try:
            issues_url = "https://api.github.com/repos/Instafill/claude-coupons/issues?state=all&per_page=15"
            async with session.get(issues_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    issues = await resp.json()
                    for item in issues:
                        body = (item.get("body") or "") + " " + (item.get("title") or "")
                        matches = re.findall(REFERRAL_REGEX, body)
                        if not matches:
                            continue

                        author = item.get("user", {}).get("login", "gh_user")
                        issue_url = item.get("html_url")

                        for code in set(matches):
                            if not db.is_link_seen(code):
                                clean_url = f"https://claude.ai/referral/{code}"
                                saved = db.save_referral(
                                    code=code,
                                    url=clean_url,
                                    source="ClaudeCoupons (GitHub Repo)",
                                    author=f"@{author}",
                                    raw_content=body[:300]
                                )
                                if saved:
                                    print(f"[HIT CLAUDE-COUPONS] Ditemukan link di repo: {clean_url}")
                                    await send_referral_alert(
                                        bot=self.bot,
                                        code=code,
                                        url=clean_url,
                                        source="ClaudeCoupons (GitHub)",
                                        author=f"@{author}",
                                        snippet=body[:150],
                                        source_url=issue_url
                                    )
        except Exception:
            pass

        # 2. Cek Commits terbaru
        try:
            commits_url = "https://api.github.com/repos/Instafill/claude-coupons/commits?per_page=10"
            async with session.get(commits_url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    commits = await resp.json()
                    for c in commits:
                        commit_msg = c.get("commit", {}).get("message", "")
                        matches = re.findall(REFERRAL_REGEX, commit_msg)
                        if not matches:
                            continue

                        author = c.get("author", {}).get("login", "contributor") if c.get("author") else "contributor"
                        commit_url = c.get("html_url")

                        for code in set(matches):
                            if not db.is_link_seen(code):
                                clean_url = f"https://claude.ai/referral/{code}"
                                saved = db.save_referral(
                                    code=code,
                                    url=clean_url,
                                    source="ClaudeCoupons (Commit)",
                                    author=f"@{author}",
                                    raw_content=commit_msg[:300]
                                )
                                if saved:
                                    print(f"[HIT CLAUDE-COUPONS] Ditemukan link di commit: {clean_url}")
                                    await send_referral_alert(
                                        bot=self.bot,
                                        code=code,
                                        url=clean_url,
                                        source="ClaudeCoupons (Commit)",
                                        author=f"@{author}",
                                        snippet=commit_msg[:150],
                                        source_url=commit_url
                                    )
        except Exception:
            pass

    async def scan_website(self, session: aiohttp.ClientSession):
        """Pantau website live ClaudeCoupons.com."""
        url = "https://claudecoupons.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    html_text = await resp.text()
                    matches = re.findall(REFERRAL_REGEX, html_text)
                    if matches:
                        for code in set(matches):
                            if not db.is_link_seen(code):
                                clean_url = f"https://claude.ai/referral/{code}"
                                saved = db.save_referral(
                                    code=code,
                                    url=clean_url,
                                    source="ClaudeCoupons.com Web",
                                    author="ClaudeCoupons Community",
                                    raw_content="Drop from claudecoupons.com board"
                                )
                                if saved:
                                    print(f"[HIT CLAUDE-COUPONS] Ditemukan link di website: {clean_url}")
                                    await send_referral_alert(
                                        bot=self.bot,
                                        code=code,
                                        url=clean_url,
                                        source="ClaudeCoupons.com",
                                        author="Community Exchange",
                                        snippet="Pass released on ClaudeCoupons board",
                                        source_url="https://claudecoupons.com"
                                    )
        except Exception:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] ClaudeCoupons (Instafill Repo & Web) Scanner aktif...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                await self.scan_github_repo(session)
                await self.scan_website(session)
                await asyncio.sleep(self.interval)

    def stop(self):
        self.running = False

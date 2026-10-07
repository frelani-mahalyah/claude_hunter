import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot

from hunter_config import MONITORED_SUBREDDITS, INTERVAL_REDDIT, AI_TARGETS
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
]

class RedditWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.ua_index = 0

    def get_headers(self):
        self.ua_index = (self.ua_index + 1) % len(USER_AGENTS)
        return {
            "User-Agent": USER_AGENTS[self.ua_index],
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        }

    async def scan_feed(self, session: aiohttp.ClientSession, url: str, subreddit: str, feed_type: str):
        try:
            async with session.get(url, headers=self.get_headers(), timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 429:
                    # Rate limited - slow down
                    return 5
                if resp.status != 200:
                    return 0

                text = await resp.text()
                # Parse XML Atom Feed
                soup = BeautifulSoup(text, "xml")
                entries = soup.find_all("entry")

                for entry in entries:
                    content_elem = entry.find("content")
                    title_elem = entry.find("title")
                    author_elem = entry.find("author")
                    link_elem = entry.find("link")

                    author_name = "reddit_user"
                    if author_elem:
                        name_tag = author_elem.find("name")
                        if name_tag and name_tag.text:
                            author_name = name_tag.text.strip().lstrip("/u/")
                    author = f"u/{author_name}"

                    post_url = f"https://reddit.com/r/{subreddit}"
                    if link_elem and link_elem.get("href"):
                        post_url = link_elem["href"]

                    raw_text = ""
                    if title_elem and title_elem.text:
                        raw_text += title_elem.text + " "
                    if content_elem and content_elem.text:
                        raw_text += content_elem.text

                    for target_name, config in AI_TARGETS.items():
                        matches = re.findall(config["pattern"], raw_text)
                        for code in set(matches):
                            if not db.is_link_seen(code):
                                clean_url = config["base_url"].format(code)
                                saved = db.save_referral(
                                    code=code,
                                    url=clean_url,
                                    source=f"Reddit (r/{subreddit} {feed_type})",
                                    author=author,
                                    raw_content=raw_text[:300],
                                    target_name=target_name
                                )
                                if saved:
                                    print(f"[HIT REDDIT {target_name}] Ditemukan link di r/{subreddit}: {clean_url}")
                                    await send_referral_alert(
                                        bot=self.bot,
                                        code=code,
                                        url=clean_url,
                                        source=f"Reddit r/{subreddit}",
                                        author=author,
                                        snippet=raw_text[:150],
                                        source_url=post_url,
                                        target_name=target_name
                                    )
                return 0
        except Exception as e:
            # Silent skip or log error
            return 0

    async def run(self):
        self.running = True
        print("[WORKER] Reddit Scanner aktif (Comments & Posts realtime)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                for sub in MONITORED_SUBREDDITS:
                    if not self.running:
                        break

                    # 1. Cek Komentar Terbaru (tempat paling sering drop guest pass)
                    comments_url = f"https://www.reddit.com/r/{sub}/comments/.rss?limit=25"
                    penalty = await self.scan_feed(session, comments_url, sub, "Comments")
                    if penalty > 0:
                        await asyncio.sleep(penalty)

                    # 2. Cek Postingan Baru
                    posts_url = f"https://www.reddit.com/r/{sub}/new/.rss?limit=15"
                    penalty = await self.scan_feed(session, posts_url, sub, "Posts")
                    if penalty > 0:
                        await asyncio.sleep(penalty)

                    await asyncio.sleep(1.5)

                await asyncio.sleep(INTERVAL_REDDIT)

    def stop(self):
        self.running = False

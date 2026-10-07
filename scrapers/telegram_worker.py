import asyncio
import re
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot

from hunter_config import DEFAULT_TELEGRAM_CHANNELS, INTERVAL_TELEGRAM, AI_TARGETS
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

class TelegramChannelWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        # Inisialisasi daftar channel default ke database jika masih kosong
        self._init_default_channels()

    def _init_default_channels(self):
        existing = db.get_monitored_channels()
        if not existing:
            for ch in DEFAULT_TELEGRAM_CHANNELS:
                db.add_monitored_channel(ch)

    async def scan_channel(self, session: aiohttp.ClientSession, channel_name: str):
        url = f"https://t.me/s/{channel_name}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }

        try:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return

                html_text = await resp.text()
                soup = BeautifulSoup(html_text, "html.parser")
                messages = soup.find_all("div", class_="tgme_widget_message")

                for msg in messages:
                    text_div = msg.find("div", class_="tgme_widget_message_text")
                    if not text_div:
                        continue
                    content = text_div.get_text()
                    date_a = msg.find("a", class_="tgme_widget_message_date")
                    msg_url = date_a.get("href") if date_a else f"https://t.me/{channel_name}"

                    for target_name, config in AI_TARGETS.items():
                        matches = re.findall(config["pattern"], content)
                        for code in set(matches):
                            if not db.is_link_seen(code):
                                clean_url = config["base_url"].format(code)
                                saved = db.save_referral(
                                    code=code,
                                    url=clean_url,
                                    source="Telegram Channel",
                                    author=f"@{channel_name}",
                                    raw_content=content[:300],
                                    target_name=target_name
                                )
                                if saved:
                                    print(f"[HIT TELEGRAM {target_name}] Ditemukan link di @{channel_name}: {clean_url}")
                                    await send_referral_alert(
                                        bot=self.bot,
                                        code=code,
                                        url=clean_url,
                                        source="Telegram",
                                        author=f"@{channel_name}",
                                        snippet=content[:150],
                                        source_url=msg_url,
                                        target_name=target_name
                                    )
        except Exception as e:
            pass

    async def run(self):
        self.running = True
        print("[WORKER] Telegram Channels Scanner aktif (Web preview mode)...")

        async with aiohttp.ClientSession() as session:
            while self.running:
                channels = db.get_monitored_channels()
                for ch in channels:
                    if not self.running:
                        break
                    await self.scan_channel(session, ch)
                    await asyncio.sleep(1.0)

                await asyncio.sleep(INTERVAL_TELEGRAM)

    def stop(self):
        self.running = False

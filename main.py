"""
Claude Referral Hunter — GitHub Actions Mode
Berjalan selama MAX_RUNTIME detik lalu exit bersih.
GitHub Actions cron akan restart otomatis setiap 5.5 jam.
Notifikasi dikirim ke @yokgas_bot (gabungan dengan Gemini scanner).
"""
import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from telegram import Bot

from hunter_config import TELEGRAM_BOT_TOKEN, DEFAULT_CHAT_ID
from database import HunterDatabase
from scrapers.reddit_worker import RedditWorker
from scrapers.telegram_worker import TelegramChannelWorker
from scrapers.hn_worker import HackerNewsWorker
from scrapers.github_worker import GitHubWorker
from scrapers.claudecoupons_worker import ClaudeCouponsWorker

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.WARNING
)
logger = logging.getLogger("ClaudeHunter")

# Maksimal waktu jalan sebelum exit bersih (5.5 jam = 19800 detik)
MAX_RUNTIME = int(os.environ.get("MAX_RUNTIME", str(5 * 3600 + 30 * 60)))

db = HunterDatabase()

async def send_startup_msg(bot: Bot):
    """Kirim pesan startup ke yokgas_bot."""
    try:
        await bot.send_message(
            chat_id=DEFAULT_CHAT_ID,
            text=(
                "🦅 <b>CLAUDE REFERRAL HUNTER AKTIF</b>\n\n"
                "📡 Memantau 5 sumber secara real-time:\n"
                "• Reddit (r/ClaudeAI, r/ClaudeCode, dll)\n"
                "• Telegram Channels\n"
                "• HackerNews\n"
                "• GitHub (claude-coupons repo)\n"
                "• ClaudeCoupons.com\n\n"
                f"⏱ Sesi ini berjalan selama ~{MAX_RUNTIME//3600} jam {(MAX_RUNTIME%3600)//60} menit."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[WARN] Gagal kirim startup msg: {e}")

async def send_shutdown_msg(bot: Bot, links_found: int):
    """Kirim pesan akhir sesi."""
    try:
        await bot.send_message(
            chat_id=DEFAULT_CHAT_ID,
            text=(
                "⏸ <b>Sesi Claude Hunter Selesai</b>\n\n"
                f"🔗 Link ditemukan sesi ini: <b>{links_found}</b>\n"
                "⏳ Bot akan otomatis restart dalam beberapa menit via jadwal GitHub Actions."
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[WARN] Gagal kirim shutdown msg: {e}")

async def main():
    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN belum diatur!")
        sys.exit(1)

    print("=" * 55)
    print("     CLAUDE REFERRAL HUNTER (GitHub Actions Mode)     ")
    print("=" * 55)
    print(f"Bot Token : ...{TELEGRAM_BOT_TOKEN[-8:]}")
    print(f"Chat ID   : {DEFAULT_CHAT_ID}")
    print(f"Max Runtime: {MAX_RUNTIME // 60} menit")
    print("=" * 55)

    # Register default subscriber
    db.add_subscriber(DEFAULT_CHAT_ID)

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    await send_startup_msg(bot)

    # Inisialisasi workers (tanpa TwitterWorker — perlu auth khusus)
    workers = [
        RedditWorker(bot),
        TelegramChannelWorker(bot),
        HackerNewsWorker(bot),
        GitHubWorker(bot),
        ClaudeCouponsWorker(bot),
    ]

    start_time = time.time()
    links_before = db.get_stats().get("total_referrals", 0)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Seluruh 5 mesin scraper aktif...")

    # Jalankan semua worker sebagai task asyncio
    tasks = [asyncio.create_task(w.run()) for w in workers]

    # Tunggu sampai MAX_RUNTIME tercapai
    try:
        await asyncio.sleep(MAX_RUNTIME)
    except asyncio.CancelledError:
        pass

    # Stop semua worker
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Waktu habis. Menghentikan worker...")
    for w in workers:
        try:
            w.stop()
        except Exception:
            pass

    # Cancel semua task
    for t in tasks:
        t.cancel()

    await asyncio.gather(*tasks, return_exceptions=True)

    links_after = db.get_stats().get("total_referrals", 0)
    links_found = max(0, links_after - links_before)
    elapsed = int(time.time() - start_time)

    print(f"\n[DONE] Sesi selesai. Runtime: {elapsed//60}m {elapsed%60}s | Link ditemukan: {links_found}")
    await send_shutdown_msg(bot, links_found)

if __name__ == "__main__":
    asyncio.run(main())

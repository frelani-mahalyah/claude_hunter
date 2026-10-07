import asyncio
import logging
import sys
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    Application
)

from hunter_config import TELEGRAM_BOT_TOKEN, DEFAULT_CHAT_ID
from database import HunterDatabase
from notifier import send_referral_alert, build_alert_message, build_inline_keyboard
from scrapers.reddit_worker import RedditWorker
from scrapers.telegram_worker import TelegramChannelWorker
from scrapers.twitter_worker import TwitterWorker
from scrapers.hn_worker import HackerNewsWorker
from scrapers.github_worker import GitHubWorker
from scrapers.claudecoupons_worker import ClaudeCouponsWorker

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("ClaudeHunter")

db = HunterDatabase()
START_TIME = datetime.now()

# Daftar Worker Instance
workers = []

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    db.add_subscriber(chat_id)

    welcome_text = (
        "🦅 <b>CLAUDE PRO GUEST PASS HUNTER — BOT AKTIF!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Bot ini berfokus penuh memantau secara real-time link undangan & guest pass:\n\n"
        "• 🎁 <b>Claude Pro 7-Day Free Pass</b> (<code>claude.ai/referral/...</code>)\n\n"
        "📡 <b>6 Jalur Pantauan Khusus Claude (24/7):</b>\n"
        "• X / Twitter (Live GraphQL stream)\n"
        "• Reddit (r/ClaudeAI, r/ClaudeCode, r/ClaudeCoding, r/Anthropic)\n"
        "• Telegram Channels (@claudereferral, @claudeprofree, dll)\n"
        "• Instafill/claude-coupons (GitHub Commits, Issues & PRs)\n"
        "• ClaudeCoupons.com Community Board\n"
        "• HackerNews Algolia & GitHub Global Search\n\n"
        "🔔 <i>Setiap link Claude baru muncul, bot akan LANGSUNG mengirimkannya ke chat ini agar Anda bisa 1-klik klaim sebelum kuotanya habis!</i>\n\n"
        "<b>Perintah Tersedia:</b>\n"
        "📊 /status - Cek statistik & total link tertangkap\n"
        "📋 /channels - Daftar channel Telegram yang dipantau\n"
        "➕ /add_channel &lt;nama&gt; - Tambah channel Telegram baru\n"
        "➖ /del_channel &lt;nama&gt; - Hapus channel Telegram\n"
        "🕒 /recent - Lihat link referral terbaru\n"
        "🧪 /test - Uji coba tampilan alert"
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = db.get_stats()
    uptime = str(datetime.now() - START_TIME).split(".")[0]

    sources_str = "\n".join([f"  • {k}: <b>{v}</b> link" for k, v in stats["by_source"].items()]) or "  • Belum ada link baru"

    text = (
        "📊 <b>STATISTIK CLAUDE PRO REFERRAL HUNTER</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Uptime:</b> {uptime}\n"
        f"👥 <b>Subscriber Aktif:</b> {stats['active_subscribers']} chat\n"
        f"🎯 <b>Total Link Claude Ditemukan:</b> {stats['total_referrals']} link\n\n"
        f"<b>Rincian Sumber:</b>\n{sources_str}\n\n"
        "🟢 <i>Semua 6 mesin scraper (Twitter, Reddit, Telegram, HN, GitHub, ClaudeCoupons) fokus 100% memantau Claude.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML")

async def cmd_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channels = db.get_monitored_channels()
    if not channels:
        await update.message.reply_text("📋 Belum ada channel Telegram yang dipantau. Gunakan /add_channel <nama_channel>.")
        return

    list_str = "\n".join([f"• @{ch} (https://t.me/{ch})" for ch in channels])
    text = (
        "📋 <b>DAFTAR CHANNEL TELEGRAM YANG DIPANTAU</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{list_str}\n\n"
        "💡 <i>Gunakan <code>/add_channel &lt;username&gt;</code> untuk menambah channel baru.</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def cmd_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format salah! Contoh: <code>/add_channel claudereferral</code>", parse_mode="HTML")
        return

    channel_name = context.args[0].strip().lstrip("@")
    success = db.add_monitored_channel(channel_name)
    if success:
        await update.message.reply_text(f"✅ Channel <b>@{channel_name}</b> berhasil ditambahkan ke daftar pantauan!", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ Gagal menambahkan channel @{channel_name}.")

async def cmd_del_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format salah! Contoh: <code>/del_channel claudereferral</code>", parse_mode="HTML")
        return

    channel_name = context.args[0].strip().lstrip("@")
    success = db.remove_monitored_channel(channel_name)
    if success:
        await update.message.reply_text(f"🗑 Channel <b>@{channel_name}</b> telah dihapus dari daftar pantauan.", parse_mode="HTML")
    else:
        await update.message.reply_text(f"⚠️ Channel @{channel_name} tidak ditemukan di database.")

async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    recents = db.get_recent_referrals(limit=6)
    if not recents:
        await update.message.reply_text("🕒 Belum ada referral yang tertangkap sejak bot dijalankan.")
        return

    lines = []
    for r in recents:
        tgt = r.get('target_name', 'Claude')
        lines.append(
            f"🎯 <b>[{tgt}]</b> <code>{r['code']}</code>\n"
            f"👤 {r['author']} · [{r['source']}]\n"
            f"🔗 {r['url']}\n"
        )

    text = "🕒 <b>REFERRAL TERBARU YANG DITEMUKAN:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
    await update.message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True)

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kirim sampel notifikasi untuk menguji format tampilan."""
    sample_code = "demo_SAMPLE7dayPASS"
    sample_url = f"https://claude.ai/referral/{sample_code}"
    alert_text = build_alert_message(
        code=sample_code,
        source="X/Twitter (Demo)",
        author="@DemoUserAI",
        snippet="Here is a free Claude Pro 7-day guest pass invite!",
        discovered_at=datetime.now()
    )
    markup = build_inline_keyboard(sample_url, "https://x.com")
    await update.message.reply_text(
        text=alert_text,
        parse_mode="HTML",
        reply_markup=markup,
        disable_web_page_preview=False
    )

async def start_workers(app: Application):
    """Jalankan semua background worker secara concurrent di event loop."""
    bot = app.bot

    # Daftarkan default chat ID jika ada
    if DEFAULT_CHAT_ID:
        db.add_subscriber(DEFAULT_CHAT_ID)
        print(f"[✅ INIT] Default subscriber ID {DEFAULT_CHAT_ID} terdaftar.")

    # Inisialisasi workers
    workers.append(RedditWorker(bot))
    workers.append(TelegramChannelWorker(bot))
    workers.append(TwitterWorker(bot))
    workers.append(HackerNewsWorker(bot))
    workers.append(GitHubWorker(bot))
    workers.append(ClaudeCouponsWorker(bot))

    # Jalankan worker di background task
    for w in workers:
        asyncio.create_task(w.run())

    print("[HUNTER READY] Seluruh 6 mesin pemantau aktif memburu link Claude Referral!")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN belum diatur di config.py!")
        sys.exit(1)

    print("=====================================================")
    print("        CLAUDE REFERRAL MULTI-SOURCE HUNTER          ")
    print("=====================================================")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(start_workers).build()

    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("channels", cmd_channels))
    app.add_handler(CommandHandler("add_channel", cmd_add_channel))
    app.add_handler(CommandHandler("del_channel", cmd_del_channel))
    app.add_handler(CommandHandler("recent", cmd_recent))
    app.add_handler(CommandHandler("test", cmd_test))

    print("[*] Bot Telegram aktif. Menunggu perintah dan scanning live...")
    app.run_polling()

if __name__ == "__main__":
    main()

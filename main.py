import asyncio
import html
import logging
import os
import sys
import time
from datetime import datetime
import requests

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    Application,
)

from hunter_config import TELEGRAM_BOT_TOKEN, DEFAULT_CHAT_ID
from database import HunterDatabase
from notifier import send_referral_alert, build_alert_message, build_inline_keyboard, format_time_diff, parse_datetime
from scrapers.reddit_worker import RedditWorker
from scrapers.telegram_worker import TelegramChannelWorker
from scrapers.hn_worker import HackerNewsWorker
from scrapers.github_worker import GitHubWorker
from scrapers.claudecoupons_worker import ClaudeCouponsWorker
from scrapers.gemini_worker import GeminiWorker

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("YokgasHunter")

db = HunterDatabase()
START_TIME = datetime.now()
workers = []

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Menu tombol interaktif utama."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📜 5 Link Claude Terbaru", callback_data="btn_history_claude"),
            InlineKeyboardButton("💎 Link Gemini Terbaru", callback_data="btn_history_gemini")
        ],
        [
            InlineKeyboardButton("📊 Cek Status & Statistik", callback_data="btn_status"),
            InlineKeyboardButton("🧪 Tes Notifikasi", callback_data="btn_test")
        ],
        [
            InlineKeyboardButton("🔄 Refresh Menu", callback_data="btn_refresh")
        ]
    ])

def format_history_text(limit: int = 5) -> tuple[str, InlineKeyboardMarkup]:
    """Menyusun teks rekapan 5 link Claude referral terbaru."""
    recents = db.get_recent_referrals(limit=limit)
    if not recents:
        return (
            "🕒 <b>REKAPAN LINK REFERRAL CLAUDE PRO</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Belum ada link Claude yang tersimpan di sesi database ini.\n"
            "Scraper sedang memantau secara live di Reddit, Telegram, GitHub, HN, & ClaudeCoupons 24/7.\n"
            "Begitu link pertama muncul, bot akan langsung kirim ke sini!",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh History", callback_data="btn_history_claude")]])
        )

    lines = [
        "🕒 <b>REKAPAN 5 LINK REFERRAL CLAUDE TERBARU</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<i>(Diurutkan dari yang paling baru ditemukan)</i>\n"
    ]

    buttons = []
    for idx, r in enumerate(recents, start=1):
        dt = parse_datetime(r.get("discovered_at"))
        dt_str = dt.strftime("%d %b %Y, %H:%M:%S WIB") if dt else "Baru saja"
        time_ago = format_time_diff(r.get("discovered_at"))
        code = r.get("code", "")
        author = html.escape(str(r.get("author", "Anon")).lstrip("@"))
        source = html.escape(str(r.get("source", "Web")))
        url = r.get("url", f"https://claude.ai/referral/{code}")

        lines.append(
            f"<b>{idx}. 🎁 Claude Pro 7-Day Guest Pass</b>\n"
            f"   🔗 Kode : <code>{code}</code>\n"
            f"   👤 Sumber: @{author} · <code>[{source}]</code>\n"
            f"   ⏱ Waktu : <b>{dt_str}</b> <i>({time_ago})</i>\n"
        )
        buttons.append([InlineKeyboardButton(f"⚡ Klaim Link #{idx} ({code[:10]}...)", url=url)])

    buttons.append([InlineKeyboardButton("🔄 Refresh History", callback_data="btn_history_claude")])
    buttons.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="btn_refresh")])

    text = "\n".join(lines) + "\n💡 <i>Klik tombol di atas untuk langsung klaim sebelum kuotanya hangus!</i>"
    return text, InlineKeyboardMarkup(buttons)

def format_gemini_history_text(limit: int = 5) -> tuple[str, InlineKeyboardMarkup]:
    """Menyusun teks rekapan link Gemini Pro 18 bulan."""
    gemini_links = db.get_recent_gemini_links(limit=limit)
    if not gemini_links:
        return (
            "💎 <b>REKAPAN LINK GOOGLE GEMINI PRO 18 BULAN</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Belum ada link Gemini yang tembus di sesi ini.\n"
            "Scanner sedang memindai 15 panel Firebase & meneruskan SMS OTP secara real-time non-stop 24 jam.\n"
            "Begitu link aktivasi didapatkan, bot akan langsung mengirimkannya ke sini!",
            InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="btn_history_gemini")]])
        )

    lines = [
        "💎 <b>REKAPAN LINK GOOGLE GEMINI PRO 18 BULAN</b>",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "<i>(Hasil tembus scanning panel Jio & OTP Forwarder)</i>\n"
    ]
    buttons = []
    for idx, g in enumerate(gemini_links, start=1):
        dt = parse_datetime(g.get("discovered_at"))
        dt_str = dt.strftime("%d %b %Y, %H:%M:%S WIB") if dt else "Baru saja"
        time_ago = format_time_diff(g.get("discovered_at"))
        ending = g.get("mobile_ending", "????")
        url = g.get("url", "")
        lines.append(
            f"<b>{idx}. 💎 Gemini Pro 18 Bulan</b>\n"
            f"   📱 Device Ending: <code>{ending}</code>\n"
            f"   ⏱ Waktu Dapat   : <b>{dt_str}</b> <i>({time_ago})</i>\n"
        )
        buttons.append([InlineKeyboardButton(f"⚡ Klaim Gemini #{idx}", url=url)])

    buttons.append([InlineKeyboardButton("🔄 Refresh", callback_data="btn_history_gemini")])
    buttons.append([InlineKeyboardButton("🔙 Menu Utama", callback_data="btn_refresh")])
    text = "\n".join(lines)
    return text, InlineKeyboardMarkup(buttons)

# ==================== TELEGRAM COMMAND HANDLERS ====================

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /start untuk user publik baru & lama."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    first_name = html.escape(user.first_name if user else "Kawan")

    # Otomatis daftarkan user ke database subscriber publik
    db.add_subscriber(chat_id)

    welcome_text = (
        f"👋 <b>Halo, {first_name}! Selamat Datang di Yokgas Hunter Bot!</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🤖 Bot ini beroperasi <b>24 Jam Non-Stop</b> memantau dan memburu promo AI premium secara live:\n\n"
        "📢 <b>Apa yang akan kamu dapatkan di sini?</b>\n"
        "1. 🎁 <b>Claude Pro 7-Day Free Guest Pass</b>\n"
        "   • Trial resmi Claude Pro dari Anthropic (<code>claude.ai/referral/...</code>)\n"
        "   • Dipantau real-time dari 5 sumber (Reddit, Telegram, GitHub, HN, ClaudeCoupons)\n\n"
        "2. 💎 <b>Google Gemini Pro 18 Bulan</b>\n"
        "   • Hasil tembus scan 15 panel Jio & forwarder SMS India\n\n"
        "✅ <b>Status Kamu:</b> <code>Aktif Terdaftar Sebagai Penerima Notifikasi</code>\n"
        "🔔 <i>Setiap kali ada link baru yang tembus, bot akan LANGSUNG mengirimkannya ke chat ini secara otomatis agar kamu bisa 1-klik klaim sebelum kuotanya hangus!</i>\n\n"
        "👇 <b>Silakan pilih menu di bawah:</b>"
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
        disable_web_page_preview=True
    )

async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /history untuk melihat 5 link Claude terbaru."""
    chat_id = update.effective_chat.id
    db.add_subscriber(chat_id)
    text, markup = format_history_text(limit=5)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)

async def cmd_gemini(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /gemini untuk melihat link Gemini 18 bulan terbaru."""
    chat_id = update.effective_chat.id
    db.add_subscriber(chat_id)
    text, markup = format_gemini_history_text(limit=5)
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /status untuk melihat kondisi scanner dan subscriber publik."""
    chat_id = update.effective_chat.id
    db.add_subscriber(chat_id)
    stats = db.get_stats()
    uptime = str(datetime.now() - START_TIME).split(".")[0]
    sources_str = "\n".join([f"  • {k}: <b>{v}</b> link" for k, v in stats["by_source"].items()]) or "  • Belum ada link baru"

    text = (
        "📊 <b>STATISTIK & MONITORING YOKGAS BOT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ <b>Uptime:</b> {uptime}\n"
        f"👥 <b>Total Subscriber Publik:</b> {stats['active_subscribers']} user\n"
        f"🎯 <b>Total Link Claude Ditemukan:</b> {stats['total_referrals']} link\n"
        f"💎 <b>Total Link Gemini Ditemukan:</b> {stats.get('total_gemini', 0)} link\n\n"
        f"<b>Rincian Sumber Claude:</b>\n{sources_str}\n\n"
        "🟢 <b>Status Sistem:</b> 6 Mesin Scraper Aktif 24/7 Non-Stop\n"
        "<i>(Reddit, Telegram, HackerNews, GitHub, ClaudeCoupons, dan Jio Gemini Panels)</i>"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())

async def cmd_test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler /test untuk melihat contoh tampilan notifikasi."""
    sample_code = "demo_SAMPLE7dayPASS"
    sample_url = f"https://claude.ai/referral/{sample_code}"
    alert_text = build_alert_message(
        code=sample_code,
        source="Reddit r/ClaudeAI (Demo)",
        author="@DemoUser",
        snippet="Here is my Claude Pro guest pass trial link for anyone interested!",
        discovered_at=datetime.now(),
        target_name="Claude",
        url=sample_url
    )
    markup = build_inline_keyboard(sample_url, "https://reddit.com")
    await update.message.reply_text(text=alert_text, parse_mode="HTML", reply_markup=markup)

async def on_button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler callback inline keyboard."""
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    db.add_subscriber(chat_id)

    if data == "btn_history_claude":
        text, markup = format_history_text(limit=5)
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            pass
    elif data == "btn_history_gemini":
        text, markup = format_gemini_history_text(limit=5)
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            pass
    elif data == "btn_status":
        stats = db.get_stats()
        uptime = str(datetime.now() - START_TIME).split(".")[0]
        sources_str = "\n".join([f"  • {k}: <b>{v}</b> link" for k, v in stats["by_source"].items()]) or "  • Belum ada link baru"
        text = (
            "📊 <b>STATISTIK & MONITORING YOKGAS BOT</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏱ <b>Uptime:</b> {uptime}\n"
            f"👥 <b>Total Subscriber Publik:</b> {stats['active_subscribers']} user\n"
            f"🎯 <b>Total Link Claude:</b> {stats['total_referrals']} link\n"
            f"💎 <b>Total Link Gemini:</b> {stats.get('total_gemini', 0)} link\n\n"
            f"<b>Rincian Sumber Claude:</b>\n{sources_str}\n\n"
            "🟢 <b>Status:</b> Seluruh 6 Scraper Aktif 24 Jam Non-Stop"
        )
        try:
            await query.edit_message_text(text=text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        except Exception:
            pass
    elif data == "btn_test":
        sample_code = "demo_SAMPLE7dayPASS"
        sample_url = f"https://claude.ai/referral/{sample_code}"
        alert_text = build_alert_message(
            code=sample_code,
            source="Reddit r/ClaudeAI (Demo)",
            author="@DemoUser",
            snippet="Here is my Claude Pro guest pass trial link for anyone interested!",
            discovered_at=datetime.now(),
            target_name="Claude",
            url=sample_url
        )
        markup = build_inline_keyboard(sample_url, "https://reddit.com")
        await query.message.reply_text(text=alert_text, parse_mode="HTML", reply_markup=markup)
    elif data == "btn_refresh":
        user_first = query.from_user.first_name or "Kawan"
        welcome_text = (
            f"👋 <b>Yokgas Hunter Bot — Menu Utama</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "🤖 Bot terus memantau 24/7 tanpa henti:\n"
            "• 🎁 <b>Claude Pro 7-Day Guest Pass</b>\n"
            "• 💎 <b>Google Gemini Pro 18 Bulan</b>\n\n"
            "Setiap ada link baru, notifikasi akan langsung masuk ke sini!\n\n"
            "👇 Pilih menu di bawah:"
        )
        try:
            await query.edit_message_text(text=welcome_text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
        except Exception:
            pass

# ==================== LIFECYCLE & BACKGROUND WORKERS ====================

async def auto_relay_watcher(app: Application):
    """
    Jika berjalan di GitHub Actions, watcher ini memantau waktu jalan.
    Saat mendekati 5 jam 15 menit, dia otomatis trigger workflow baru
    lewat GitHub Actions API agar scanning bersambung 24/7 non-stop tanpa downtime!
    """
    max_runtime = int(os.environ.get("MAX_RUNTIME", str(5 * 3600 + 15 * 60)))
    await asyncio.sleep(max_runtime)

    print("[RELAY] Batas runtime sesi tercapai. Memulai auto-relay ke GitHub Actions berikutnya...")
    gh_token = os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "frelani-mahalyah/claude_hunter")

    if gh_token:
        try:
            url = f"https://api.github.com/repos/{repo}/actions/workflows/bot.yml/dispatches"
            headers = {"Authorization": f"token {gh_token}", "Accept": "application/vnd.github.v3+json"}
            r = requests.post(url, headers=headers, json={"ref": "main"}, timeout=10)
            print(f"[RELAY] Trigger workflow baru status: {r.status_code}")
        except Exception as e:
            print(f"[RELAY ERR] Gagal trigger dispatch: {e}")

    # Hentikan bot polling dengan bersih agar GitHub Actions beralih ke commit & run berikutnya
    app.stop_running()

async def start_workers(app: Application):
    """Mulai semua 6 mesin pemantau secara concurrent di event loop."""
    bot = app.bot

    # Daftarkan default admin ID jika ada
    if DEFAULT_CHAT_ID:
        db.add_subscriber(DEFAULT_CHAT_ID)
        print(f"[INIT] Admin ID {DEFAULT_CHAT_ID} terdaftar.")

    # Inisialisasi 6 worker (5 Claude + 1 Gemini)
    workers.append(RedditWorker(bot))
    workers.append(TelegramChannelWorker(bot))
    workers.append(HackerNewsWorker(bot))
    workers.append(GitHubWorker(bot))
    workers.append(ClaudeCouponsWorker(bot))
    workers.append(GeminiWorker(bot))

    # Jalankan semua worker sebagai task background
    for w in workers:
        asyncio.create_task(w.run())

    # Jalankan watcher relay jika ada MAX_RUNTIME
    if os.environ.get("GITHUB_ACTIONS") == "true":
        asyncio.create_task(auto_relay_watcher(app))

    print("[YOKGAS HUNTER READY] Seluruh 6 mesin pemantau (Claude & Gemini) aktif 24 Jam Non-Stop!")

def main():
    if not TELEGRAM_BOT_TOKEN:
        print("[ERROR] TELEGRAM_BOT_TOKEN belum diatur!")
        sys.exit(1)

    print("=====================================================")
    print("      YOKGAS HUNTER: CLAUDE & GEMINI 24/7 BOT        ")
    print("=====================================================")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(start_workers).build()

    # Handlers Perintah
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu", cmd_start))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("claude", cmd_history))
    app.add_handler(CommandHandler("gemini", cmd_gemini))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("test", cmd_test))

    # Handlers Tombol Callback
    app.add_handler(CallbackQueryHandler(on_button_click))

    print("[*] Polling Telegram aktif untuk publik. Menunggu user dan scanning...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

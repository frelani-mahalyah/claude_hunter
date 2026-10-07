import html
from datetime import datetime
from typing import Optional, List
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from database import HunterDatabase

db = HunterDatabase()

def format_time_diff(discovered_at: Optional[datetime] = None) -> str:
    """Format selisih waktu persis seperti screenshot (e.g. '14 detik lalu', '3 menit lalu')."""
    if not discovered_at:
        return "Baru saja"
    diff = (datetime.now() - discovered_at).total_seconds()
    if diff < 60:
        return f"{int(max(1, diff))} detik lalu"
    elif diff < 3600:
        return f"{int(diff // 60)} menit lalu"
    else:
        return f"{int(diff // 3600)} jam lalu"

TARGET_METAS = {
    "Claude": {"emoji": "🎁", "desc": "7 hari Claude Pro gratis"},
    "Manus AI": {"emoji": "🤖", "desc": "500 Credits Manus AI gratis"},
    "ChatGPT": {"emoji": "🟢", "desc": "Akses ChatGPT Plus / Promo gratis"},
    "Grok": {"emoji": "⚡", "desc": "Trial SuperGrok / Grok xAI gratis"}
}

def build_alert_message(code: str, source: str, author: str, snippet: str = "", discovered_at: Optional[datetime] = None, target_name: str = "Claude", url: Optional[str] = None) -> str:
    """Membangun template HTML pesan Telegram persis seperti screenshot pengguna."""
    time_str = format_time_diff(discovered_at)
    clean_author = html.escape(author.strip().lstrip("@")) if author else "Anonymous"
    clean_snippet = html.escape(snippet.strip().replace("\n", " ")[:120]) if snippet else ""

    meta = TARGET_METAS.get(target_name, {"emoji": "🎁", "desc": "Akses gratis"})
    emoji = meta["emoji"]
    desc = meta["desc"]
    full_url = url or f"https://claude.ai/referral/{code}"

    msg = (
        f"{emoji} <b>{target_name} referral link</b> <i>({time_str})</i>\n"
        f"👤 @{clean_author}  ·  <code>[{source}]</code>\n"
        f"🔗 {full_url}\n"
    )

    if clean_snippet:
        msg += f"\n<blockquote>💡 \"{clean_snippet}...\"</blockquote>"

    msg += f"\n\n⚡ <i>Segera klik tombol di bawah untuk klaim {desc} sebelum kuota hangus!</i>"
    return msg

def build_inline_keyboard(url: str, source_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Membuat tombol interaktif klaim instan 1-klik."""
    buttons = [
        [InlineKeyboardButton("⚡ KLAIM SEKARANG (1-Click)", url=url)]
    ]
    if source_url and source_url.startswith("http"):
        buttons.append([InlineKeyboardButton("🌐 Buka Postingan Asli", url=source_url)])
    return InlineKeyboardMarkup(buttons)

async def send_referral_alert(bot: Bot, code: str, url: str, source: str, author: str, snippet: str = "", source_url: Optional[str] = None, target_name: str = "Claude"):
    """Kirim notifikasi broadcast ke semua subscriber aktif di database."""
    subscribers = db.get_subscribers()
    if not subscribers:
        print(f"[!] Tidak ada subscriber aktif untuk menerima kode: {code}")
        return

    text = build_alert_message(code, source, author, snippet, datetime.now(), target_name, url)
    reply_markup = build_inline_keyboard(url, source_url)

    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                disable_web_page_preview=False
            )
            safe_author = str(author).encode("ascii", "replace").decode("ascii")
            safe_source = str(source).encode("ascii", "replace").decode("ascii")
            print(f"[SUCCESS] Referral [{code}] terkirim ke Chat ID: {chat_id} (Sumber: {safe_source})")
        except TelegramError as e:
            print(f"[ERROR] Gagal kirim ke {chat_id}: {e}")
            if "blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                db.remove_subscriber(chat_id)
        except Exception as ex:
            pass

import html
from datetime import datetime
from typing import Optional, List, Union
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from database import HunterDatabase

db = HunterDatabase()

def parse_datetime(dt_val: Union[datetime, str, None]) -> Optional[datetime]:
    if not dt_val:
        return None
    if isinstance(dt_val, datetime):
        return dt_val
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(dt_val).split(".")[0], fmt)
        except Exception:
            continue
    return None

def format_time_diff(discovered_at: Union[datetime, str, None] = None) -> str:
    """Format selisih waktu persis (e.g. '14 detik lalu', '3 menit lalu')."""
    dt = parse_datetime(discovered_at)
    if not dt:
        return "Baru saja"
    diff = (datetime.now() - dt).total_seconds()
    if diff < 0:
        return "Baru saja"
    if diff < 60:
        return f"{int(max(1, diff))} detik lalu"
    elif diff < 3600:
        return f"{int(diff // 60)} menit lalu"
    elif diff < 86400:
        return f"{int(diff // 3600)} jam lalu"
    else:
        return f"{int(diff // 86400)} hari lalu"

TARGET_METAS = {
    "Claude": {"emoji": "🎁", "desc": "7 hari Claude Pro gratis"},
    "Manus AI": {"emoji": "🤖", "desc": "500 Credits Manus AI gratis"},
    "ChatGPT": {"emoji": "🟢", "desc": "Akses ChatGPT Plus / Promo gratis"},
    "Grok": {"emoji": "⚡", "desc": "Trial SuperGrok / Grok xAI gratis"}
}

def build_alert_message(code: str, source: str, author: str, snippet: str = "", discovered_at: Union[datetime, str, None] = None, target_name: str = "Claude", url: Optional[str] = None) -> str:
    """Template pesan Telegram broadcast Claude Referral."""
    time_str = format_time_diff(discovered_at)
    clean_author = html.escape(author.strip().lstrip("@")) if author else "Anonymous"
    clean_snippet = html.escape(snippet.strip().replace("\n", " ")[:120]) if snippet else ""

    meta = TARGET_METAS.get(target_name, {"emoji": "🎁", "desc": "Akses gratis"})
    emoji = meta["emoji"]
    desc = meta["desc"]
    full_url = url or f"https://claude.ai/referral/{code}"

    msg = (
        f"{emoji} <b>{target_name} Referral Link</b> <i>({time_str})</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 Pengirim : @{clean_author}  ·  <code>[{source}]</code>\n"
        f"🔗 Link     : {full_url}\n"
    )

    if clean_snippet:
        msg += f"\n<blockquote>💡 \"{clean_snippet}...\"</blockquote>"

    msg += f"\n\n⚡ <i>Segera klik tombol di bawah untuk klaim {desc} sebelum kuota hangus!</i>"
    return msg

def build_inline_keyboard(url: str, source_url: Optional[str] = None) -> InlineKeyboardMarkup:
    """Tombol interaktif klaim instan 1-klik."""
    buttons = [
        [InlineKeyboardButton("⚡ KLAIM CLAUDE SEKARANG (1-Click)", url=url)]
    ]
    if source_url and source_url.startswith("http"):
        buttons.append([InlineKeyboardButton("🌐 Buka Postingan Asli", url=source_url)])
    return InlineKeyboardMarkup(buttons)

async def send_referral_alert(bot: Bot, code: str, url: str, source: str, author: str, snippet: str = "", source_url: Optional[str] = None, target_name: str = "Claude"):
    """Kirim notifikasi broadcast ke SEMUA subscriber publik di database."""
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
            print(f"[BROADCAST CLAUDE] Terkirim ke chat {chat_id}: {code}")
        except TelegramError as e:
            if "blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                db.remove_subscriber(chat_id)
        except Exception:
            pass

async def send_gemini_alert(bot: Bot, url: str, mobile_ending: str = "", discovered_at: Union[datetime, str, None] = None):
    """Kirim notifikasi broadcast link Gemini Pro 18 Bulan ke SEMUA subscriber."""
    subscribers = db.get_subscribers()
    if not subscribers:
        return

    time_str = format_time_diff(discovered_at or datetime.now())
    text = (
        f"💎 <b>GOOGLE GEMINI PRO 18 BULAN — LINK AKTIVASI!</b> <i>({time_str})</i>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📱 Nomor Device : <code>ending {mobile_ending}</code>\n"
        f"🔗 Link Aktivasi: <code>{url}</code>\n\n"
        f"⚡ <i>Hasil tembus scan panel Jio! Segera klaim sebelum kuotanya habis.</i>"
    )
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡ KLAIM GEMINI 18 BULAN SEKARANG", url=url)]
    ])

    for chat_id in subscribers:
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=markup,
                disable_web_page_preview=False
            )
            print(f"[BROADCAST GEMINI] Terkirim ke chat {chat_id}: ending {mobile_ending}")
        except TelegramError as e:
            if "blocked" in str(e).lower() or "user is deactivated" in str(e).lower():
                db.remove_subscriber(chat_id)
        except Exception:
            pass

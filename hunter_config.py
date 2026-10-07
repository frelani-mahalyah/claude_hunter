import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 1. TELEGRAM BOT SETTINGS
# Menggunakan @yokgas_bot yang sama dengan Gemini scanner
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8706782960:AAFFxuOs0HoNyVpaPI56Qj42C6e4nUOEPpY")

# ID Chat penerima notifikasi (Hendra Setyawan)
DEFAULT_CHAT_ID = int(os.getenv("DEFAULT_CHAT_ID", "8403291265"))

# 2. INTERVAL POLLING (DETIK) - Dioptimasi khusus untuk Claude
INTERVAL_REDDIT = 10       # Cek Reddit posts & comments
INTERVAL_TELEGRAM = 12     # Cek Channel Telegram publik
INTERVAL_TWITTER = 10      # Cek X/Twitter Live Search (Dedicated Claude query)
INTERVAL_HACKERNEWS = 15   # Cek HackerNews Algolia
INTERVAL_GITHUB = 20       # Cek GitHub issues & repo
INTERVAL_CLAUDECOUPONS = 20 # Cek Instafill repo & claudecoupons.com

# 3. DAFTAR SUBREDDIT KHUSUS CLAUDE (REDDIT)
MONITORED_SUBREDDITS = [
    "ClaudeAI",
    "ClaudeCode",
    "ClaudeCoding",
    "Anthropic",
    "Freebies"
]

# 4. DAFTAR CHANNEL TELEGRAM PUBLIK KHUSUS CLAUDE
DEFAULT_TELEGRAM_CHANNELS = [
    "claudereferral",
    "claudeprofree",
    "claudeguestpass",
    "claude_code_passes",
    "ai_drops_channel"
]

# 5. X / TWITTER CREDENTIALS
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN", "f41a55d2ef5847c3e80cbd472f117e4caad1d135")
TWITTER_CT0 = os.getenv("TWITTER_CT0", "2c0026179c994cd34cfb129abbd63d6d2078c8082269b62b9d771413fc9ad287a36aa620d34d4ec9239e7b3ca102e599a951c51d2ee156026bb082ca612cce048ebefa23e05d739e922d26e7a86d0b64")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# 6. TARGET AI REFERRAL - FOKUS EKSKLUSIF CLAUDE PRO
AI_TARGETS = {
    "Claude": {
        "pattern": r"https?://(?:www\.)?claude\.ai/referral/([a-zA-Z0-9_-]+)",
        "base_url": "https://claude.ai/referral/{}",
        "twitter_query": "claude.ai/referral",
        "emoji": "🎁",
        "description": "Claude Pro 7-Day Free Guest Pass"
    }
}

# Pola regex gabungan untuk scanning cepat
REFERRAL_REGEX = r"https?://(?:www\.)?claude\.ai/referral/([a-zA-Z0-9_-]+)"

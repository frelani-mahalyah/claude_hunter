import os
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load local .env jika ada
env_file = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_file):
    try:
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() not in os.environ:
                        os.environ[k.strip()] = v.strip()
    except Exception:
        pass

# 1. TELEGRAM BOT SETTINGS
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT_ID = int(os.getenv("DEFAULT_CHAT_ID") or "8403291265")

# 2. INTERVAL POLLING (DETIK)
INTERVAL_REDDIT = 10
INTERVAL_TELEGRAM = 12
INTERVAL_TWITTER = 10
INTERVAL_HACKERNEWS = 15
INTERVAL_GITHUB = 20
INTERVAL_CLAUDECOUPONS = 20
INTERVAL_WAYBACK = 60
INTERVAL_NOTE = 30

# 3. DAFTAR SUBREDDIT KHUSUS CLAUDE
MONITORED_SUBREDDITS = [
    "ClaudeAI",
    "ClaudeCode",
    "ClaudeCoding",
    "Anthropic",
    "Freebies"
]

# 4. DAFTAR CHANNEL TELEGRAM PUBLIK
DEFAULT_TELEGRAM_CHANNELS = [
    "claudereferral",
    "claudeprofree",
    "claudeguestpass",
    "claude_code_passes",
    "ai_drops_channel"
]

# 5. X / TWITTER CREDENTIALS
TWITTER_AUTH_TOKEN = os.getenv("TWITTER_AUTH_TOKEN", "")
TWITTER_CT0 = os.getenv("TWITTER_CT0", "")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "")
TWITTER_PASSWORD = os.getenv("TWITTER_PASSWORD", "")

# 6. TARGET AI REFERRAL
AI_TARGETS = {
    "Claude": {
        "pattern": r"https?://(?:www\.)?claude\.ai/referral/([a-zA-Z0-9_-]+)",
        "base_url": "https://claude.ai/referral/{}",
        "twitter_query": "claude.ai/referral",
        "emoji": "🎁",
        "description": "Claude Pro 7-Day Free Guest Pass"
    }
}

REFERRAL_REGEX = r"https?://(?:www\.)?claude\.ai/referral/([a-zA-Z0-9_-]+)"

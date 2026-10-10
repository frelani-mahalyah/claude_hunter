import os
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Tuple

DB_PATH = os.path.join(os.path.dirname(__file__), "claude_referrals.db")

class HunterDatabase:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Table 1: Link Referral yang ditemukan (Claude & AI lainnya)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS referrals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    author TEXT,
                    raw_content TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    notified INTEGER DEFAULT 1,
                    target_name TEXT DEFAULT 'Claude'
                )
            """)

            # Table 2: Link Google Gemini Pro 18 Bulan dari panel Jio
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS gemini_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE NOT NULL,
                    mobile_ending TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table 3: Daftar Channel Telegram Publik yang dipantau
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS monitored_channels (
                    channel_name TEXT PRIMARY KEY,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Table 4: Daftar Penerima Notifikasi Publik (Chat ID Telegram)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS subscribers (
                    chat_id INTEGER PRIMARY KEY,
                    is_active INTEGER DEFAULT 1,
                    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Migrasi aman jika kolom belum ada
            try:
                cursor.execute("ALTER TABLE referrals ADD COLUMN target_name TEXT DEFAULT 'Claude'")
            except Exception:
                pass

            conn.commit()

    def is_link_seen(self, code: str) -> bool:
        """Cek apakah kode referral sudah pernah tercatat."""
        clean_code = code.strip()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM referrals WHERE code = ?", (clean_code,))
            return cursor.fetchone() is not None

    def save_referral(self, code: str, url: str, source: str, author: str, raw_content: str = "", target_name: str = "Claude") -> bool:
        """Simpan referral baru. Mengembalikan True jika berhasil (belum pernah ada)."""
        clean_code = code.strip()
        if self.is_link_seen(clean_code):
            return False

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO referrals (code, url, source, author, raw_content, discovered_at, target_name)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (clean_code, url, source, author, raw_content[:500], now_str, target_name))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_recent_referrals(self, limit: int = 5) -> List[Dict]:
        """Ambil 5 referral terbaru yang berhasil ditangkap (urut dari terbaru)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, code, url, source, author, discovered_at, COALESCE(target_name, 'Claude') as target_name
                FROM referrals 
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    # --- Manajemen Link Google Gemini Pro 18 Bulan ---
    def is_gemini_seen(self, url: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM gemini_links WHERE url = ?", (url.strip(),))
            return cursor.fetchone() is not None

    def save_gemini_link(self, url: str, mobile_ending: str = "") -> bool:
        if not url:
            return False
        clean_url = url.strip()
        if self.is_gemini_seen(clean_url):
            return False
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO gemini_links (url, mobile_ending, discovered_at)
                    VALUES (?, ?, ?)
                """, (clean_url, mobile_ending, now_str))
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    def get_recent_gemini_links(self, limit: int = 5) -> List[Dict]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, url, mobile_ending, discovered_at
                FROM gemini_links
                ORDER BY id DESC LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict:
        """Ambil ringkasan statistik scraper Claude & Gemini."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM referrals")
            total_claude = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as total FROM gemini_links")
            total_gemini = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT source, COUNT(*) as count 
                FROM referrals 
                GROUP BY source
            """)
            by_source = {row["source"]: row["count"] for row in cursor.fetchall()}

            cursor.execute("SELECT COUNT(*) as sub_count FROM subscribers WHERE is_active = 1")
            sub_count = cursor.fetchone()["sub_count"]

            return {
                "total_referrals": total_claude,
                "total_gemini": total_gemini,
                "by_source": by_source,
                "active_subscribers": sub_count
            }

    # --- Manajemen Channel Telegram ---
    def add_monitored_channel(self, channel_name: str) -> bool:
        clean_name = channel_name.strip().lstrip("@")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT OR IGNORE INTO monitored_channels (channel_name) VALUES (?)", (clean_name,))
                conn.commit()
                return True
            except Exception:
                return False

    def remove_monitored_channel(self, channel_name: str) -> bool:
        clean_name = channel_name.strip().lstrip("@")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM monitored_channels WHERE channel_name = ?", (clean_name,))
            conn.commit()
            return cursor.rowcount > 0

    def get_monitored_channels(self) -> List[str]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_name FROM monitored_channels ORDER BY channel_name ASC")
            return [row["channel_name"] for row in cursor.fetchall()]

    # --- Manajemen Subscriber Publik ---
    def add_subscriber(self, chat_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO subscribers (chat_id, is_active)
                VALUES (?, 1)
                ON CONFLICT(chat_id) DO UPDATE SET is_active = 1
            """, (chat_id,))
            conn.commit()
            return True

    def remove_subscriber(self, chat_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE subscribers SET is_active = 0 WHERE chat_id = ?", (chat_id,))
            conn.commit()
            return True

    def get_subscribers(self) -> List[int]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT chat_id FROM subscribers WHERE is_active = 1")
            return [row["chat_id"] for row in cursor.fetchall()]

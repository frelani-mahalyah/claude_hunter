# 🦅 CLAUDE REFERRAL HUNTER BOT (MULTI-SOURCE)

Bot scraper & pemantau real-time untuk mendeteksi link **Claude Guest Pass / Referral (`claude.ai/referral/`)** dari berbagai platform publik (X/Twitter, Reddit, Telegram, Hacker News, GitHub).

Begitu ada pengguna di internet yang membagikan link referral baru (yang memberikan **7 Hari Akses Gratis Claude Pro**), bot akan langsung mem-parsing link tersebut dan mengirimkan notifikasi instan ke Telegram Anda dalam hitungan detik.

---

## 🎯 FITUR UTAMA

1. **Multi-Source Real-time Monitoring:**
   - **🐦 X / Twitter:** Memantau postingan & cuitan terbaru via Twikit (mendukung cookie `auth_token` + `ct0`) dan pencarian live.
   - **🔴 Reddit:** Memantau feed komentar dan postingan terbaru di subreddit:
     - `r/ClaudeAI`
     - `r/ClaudeCode`
     - `r/ClaudeCoding`
     - `r/Anthropic`
     - `r/ChatGPT`
     - `r/Freebies`
   - **✈️ Telegram Public Channels:** Memantau channel Telegram publik tanpa perlu login akun (menggunakan web scraper `t.me/s/<channel>`). Bisa ditambah/dihapus dinamis via chat bot!
   - **🟠 Hacker News:** Memantau API live Algolia Hacker News secara berkala.
   - **🐙 GitHub:** Memantau Issues dan Discussions publik yang membagikan pass.
   - **🎟 ClaudeCoupons / Instafill:** Memantau repo GitHub `Instafill/claude-coupons` (issues, PRs, commits) dan web board `claudecoupons.com` secara real-time.

2. **Tampilan Notifikasi Persis Seperti Screenshot:**
   - Notifikasi dilengkapi waktu relatif (`14 detik lalu`, `3 menit lalu`).
   - Username pembuat link (`@author`).
   - Sumber platform (`[X/Twitter]`, `[Reddit]`, `[Telegram]`, dll).
   - Tombol interaktif **[⚡ KLAIM SEKARANG]** untuk membuka link referral dalam 1 kali klik.

3. **Anti-Duplikat (SQLite Database):**
   - Setiap link yang masuk dicatat di `claude_referrals.db`.
   - Kode yang sama tidak akan pernah dikirim dua kali.

---

## 🚀 CARA MENJALANKAN

### Cara 1: Jalankan dengan Batch File (Windows)
Cukup klik dua kali file:
```
run_hunter.bat
```

### Cara 2: Jalankan via Terminal / CMD
```bash
cd c:\Users\PC\Videos\TELEGRAB\claude_hunter
python main.py
```

---

## ⚙️ PENGATURAN (hunter_config.py)

Buka file [hunter_config.py](file:///c:/Users/PC/Videos/TELEGRAB/claude_hunter/hunter_config.py) untuk menyesuaikan pengaturan:

```python
# 1. Token Bot Telegram (Dapatkan dari @BotFather)
TELEGRAM_BOT_TOKEN = "TOKEN_BOT_ANDA"

# 2. Chat ID Anda untuk menerima notifikasi otomatis
DEFAULT_CHAT_ID = 783262896

# 3. Kredensial X / Twitter (Opsional, untuk kecepatan maksimal scraping X)
# Dapatkan cookie 'auth_token' dan 'ct0' dari browser saat login di x.com:
TWITTER_AUTH_TOKEN = ""
TWITTER_CT0 = ""
```

---

## 📱 PERINTAH BOT TELEGRAM

Setelah bot berjalan, buka bot Anda di Telegram dan kirim perintah berikut:

| Perintah | Fungsi |
|---|---|
| `/start` | Mendaftarkan chat Anda untuk menerima notifikasi link baru |
| `/status` | Melihat status bot, total link tertangkap, dan statistik sumber |
| `/channels` | Melihat daftar channel Telegram publik yang sedang dipantau |
| `/add_channel <nama>` | Menambahkan channel Telegram baru ke daftar pantauan (misal: `/add_channel claudereferral`) |
| `/del_channel <nama>` | Menghapus channel Telegram dari daftar pantauan |
| `/recent` | Menampilkan 5 link referral terbaru yang berhasil ditangkap |
| `/test` | Mengirim contoh pesan alert untuk menguji format tampilan |

---

## 💡 TIPS MENGKLAIM LINK CEPAT
1. Siapkan browser Anda dalam kondisi sudah login ke akun Claude (akun free/baru yang belum pernah berlangganan Pro).
2. Begitu notifikasi masuk ke Telegram, langsung tekan tombol **[⚡ KLAIM SEKARANG]**.
3. Klaim pass akan langsung aktif 7 hari gratis tanpa menunggu antrean!

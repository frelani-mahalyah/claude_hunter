import asyncio
import json
import re
from datetime import datetime
from telegram import Bot
from curl_cffi import requests

from hunter_config import (
    INTERVAL_TWITTER,
    TWITTER_AUTH_TOKEN,
    TWITTER_CT0,
    AI_TARGETS
)
from database import HunterDatabase
from notifier import send_referral_alert

db = HunterDatabase()

SEARCH_QUERY_ID = "auLkqtmHqYEpRvflfvLhyQ"

class TwitterWorker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = False
        self.cookies = {}
        self.headers = {}
        self._init_session()

    def _init_session(self):
        if TWITTER_AUTH_TOKEN and TWITTER_CT0:
            self.cookies = {
                "auth_token": TWITTER_AUTH_TOKEN.strip(),
                "ct0": TWITTER_CT0.strip()
            }
            self.headers = {
                "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                "x-csrf-token": self.cookies["ct0"],
                "x-twitter-auth-type": "OAuth2Session",
                "x-twitter-active-user": "yes",
                "content-type": "application/json",
                "referer": "https://x.com/search?q=claude.ai/referral&f=live"
            }
            print("[TWITTER] Dedicated Claude Referral Scanner aktif (Real-time Live GraphQL)!")
        else:
            print("[TWITTER] Cookies Twitter belum lengkap. Mode fallback aktif.")

    def _scan_target_sync(self, target_name: str, config: dict):
        """Request synchronous ke Twitter GraphQL via curl_cffi untuk target tertentu."""
        if not self.cookies or not self.headers:
            return []

        url = f"https://x.com/i/api/graphql/{SEARCH_QUERY_ID}/SearchTimeline"
        variables = {
            "rawQuery": config["twitter_query"],
            "count": 10,
            "querySource": "typed_query",
            "product": "Latest"
        }

        pattern = config["pattern"]
        base_url_tmpl = config["base_url"]

        try:
            r = requests.post(
                url,
                headers=self.headers,
                cookies=self.cookies,
                json={"variables": variables},
                impersonate="chrome124",
                timeout=10
            )

            if r.status_code != 200:
                return []

            data = r.json()
            results = []
            instructions = data.get("data", {}).get("search_by_raw_query", {}).get("search_timeline", {}).get("timeline", {}).get("instructions", [])
            
            for inst in instructions:
                if inst.get("type") == "TimelineAddEntries":
                    for entry in inst.get("entries", []):
                        item = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                        if not item:
                            continue
                        if item.get("__typename") == "TweetWithVisibilityResults":
                            item = item.get("tweet", {})

                        # Ambil user screen name
                        user_res = item.get("core", {}).get("user_results", {}).get("result", {})
                        screen_name = (
                            user_res.get("core", {}).get("screen_name") or
                            user_res.get("legacy", {}).get("screen_name") or
                            "TwitterUser"
                        )

                        legacy = item.get("legacy", {})
                        text = legacy.get("full_text", "")
                        tweet_id = legacy.get("id_str") or item.get("rest_id", "")

                        # Expand t.co short links
                        for u in legacy.get("entities", {}).get("urls", []):
                            if u.get("expanded_url"):
                                text = text.replace(u["url"], u["expanded_url"])

                        matches = re.findall(pattern, text)
                        if matches:
                            for code in set(matches):
                                clean_url = base_url_tmpl.format(code)
                                results.append({
                                    "target_name": target_name,
                                    "code": code,
                                    "url": clean_url,
                                    "author": f"@{screen_name}",
                                    "text": text,
                                    "tweet_url": f"https://x.com/{screen_name}/status/{tweet_id}" if tweet_id else "https://x.com"
                                })
            return results
        except Exception:
            return []

    async def scan(self):
        loop = asyncio.get_running_loop()
        
        for target_name, config in AI_TARGETS.items():
            if not self.running:
                break

            hits = await loop.run_in_executor(None, self._scan_target_sync, target_name, config)
            for hit in hits:
                code = hit["code"]
                clean_url = hit["url"]
                author = hit["author"]
                text = hit["text"]
                tweet_url = hit["tweet_url"]
                tgt = hit["target_name"]

                if not db.is_link_seen(code):
                    saved = db.save_referral(
                        code=code,
                        url=clean_url,
                        source=f"X / Twitter (Live)",
                        author=author,
                        raw_content=text[:300],
                        target_name=tgt
                    )
                    if saved:
                        print(f"[HIT TWITTER {tgt}] Ditemukan link baru: {clean_url}")
                        await send_referral_alert(
                            bot=self.bot,
                            code=code,
                            url=clean_url,
                            source="X/Twitter",
                            author=author,
                            snippet=text[:150],
                            source_url=tweet_url,
                            target_name=tgt
                        )
            await asyncio.sleep(2.0)

    async def run(self):
        self.running = True
        print("[WORKER] X/Twitter Live Search Scanner Claude aktif...")

        while self.running:
            await self.scan()
            await asyncio.sleep(INTERVAL_TWITTER)

    def stop(self):
        self.running = False

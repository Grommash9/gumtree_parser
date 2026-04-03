#!/usr/bin/env python3
"""
Reddit Keyword Search — Flipping Jokes & Memes
Finds funny posts and memes from flipping/reselling communities
for use as Minecraft-style splash texts on the app homescreen.
"""

import json
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from pathlib import Path

# Configuration (same as main scraper)
CLIENT_ID = "equQMWfew9ak4nimpi2MBQ"
CLIENT_SECRET = "bwTnFcHekESh01FoAGBZoXqJVhNaSg"
USER_AGENT = "funnelboost-scraper/1.0"

# Subreddits where flipping humor lives
SUBREDDITS = [
    "Flipping",
    "FlippingUK",
    "eBaySellerAdvice",
    "ThriftStoreHauls",
    "thrifting",
    "Etsy",
    "poshmark",
    "mercari",
    "CasualUK",
    "Antiques",
    "GarageSale",
]

# Humor-focused keywords organized by theme
KEYWORDS = {
    # Death pile / hoarding jokes
    "death_pile": [
        "death pile",
        "deathpile",
        "not hoarding",
        "it's not hoarding",
        "garage full",
        "storage unit full",
        "house full of inventory",
        "living room is a warehouse",
        "spare room inventory",
        "car lives outside",
    ],

    # Money / profit humor
    "money_humor": [
        "flipping meme",
        "reseller meme",
        "revenue is not profit",
        "bought myself a job",
        "side hustle joke",
        "rich in inventory",
        "profit after fees",
        "spent more than I made",
        "told my wife it cost",
        "investment not spending",
    ],

    # Sourcing humor
    "sourcing_humor": [
        "charity shop addiction",
        "boot sale addiction",
        "thrift store addiction",
        "can't stop buying",
        "sourcing problem",
        "dumpster diving finds",
        "one man's trash",
        "garage sale funny",
        "estate sale stories",
        "best worst find",
    ],

    # Listing fatigue / work humor
    "listing_fatigue": [
        "hate listing",
        "listing burnout",
        "photography nightmare",
        "measuring everything",
        "description writing pain",
        "crosslisting hell",
        "taking photos meme",
        "list it tomorrow",
        "procrastinating listings",
    ],

    # Buyer humor
    "buyer_humor": [
        "is this still available",
        "lowball offer",
        "lowballer",
        "will you take $1",
        "no shows",
        "choosing beggars reselling",
        "worst buyer",
        "buyer stories",
        "what's your lowest",
        "I know what I have",
    ],

    # Reseller lifestyle
    "lifestyle_humor": [
        "reseller life",
        "flipper life",
        "flipping addiction",
        "thrift store finds funny",
        "reseller problems",
        "flipping problems",
        "reseller confession",
        "flipping confession",
        "reseller starter pack",
        "you might be a reseller if",
    ],

    # Shipping humor
    "shipping_humor": [
        "shipping nightmare",
        "post office run",
        "packaging everything",
        "bubble wrap life",
        "shipping cost surprise",
        "returns pain",
        "item not as described",
    ],

    # Family reactions
    "family_humor": [
        "spouse thinks I'm crazy",
        "wife hates my inventory",
        "husband hates my inventory",
        "partner flipping",
        "family thinks I hoard",
        "explain flipping to family",
        "my family doesn't understand",
    ],

    # General flipping jokes (flair:meme, flair:humor, etc.)
    "general_jokes": [
        "flair:meme",
        "flair:humor",
        "flair:funny",
        "flair:shitpost",
        "flipping joke",
        "reselling joke",
        "thrifting joke",
        "funniest flip",
        "reseller humor",
    ],
}

DATA_DIR = Path(__file__).parent / "data"


class RedditJokesSearcher:
    def __init__(self):
        self.access_token = None
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 600
        self.request_count = 0

    def get_token(self):
        """Get OAuth access token."""
        print("Getting OAuth token...")
        auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
        response = requests.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "client_credentials"},
            headers={"User-Agent": USER_AGENT}
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get token: {response.status_code}")

        data = response.json()
        if "access_token" not in data:
            raise Exception(f"No access token in response: {data}")

        self.access_token = data["access_token"]
        print(f"Token acquired (expires in {data.get('expires_in', '?')}s)")

    def handle_rate_limit(self, response):
        """Check rate limit headers and sleep if needed."""
        self.rate_limit_remaining = float(response.headers.get('x-ratelimit-remaining', 100))
        self.rate_limit_reset = float(response.headers.get('x-ratelimit-reset', 600))
        self.request_count += 1

        if self.rate_limit_remaining < 10:
            sleep_time = self.rate_limit_reset + 5
            print(f"\n  [RATE LIMIT] Only {self.rate_limit_remaining:.0f} remaining, sleeping {sleep_time:.0f}s...")
            time.sleep(sleep_time)
        elif self.rate_limit_remaining < 30:
            print(f"  [RATE LIMIT] {self.rate_limit_remaining:.0f} remaining, slowing down...")
            time.sleep(2)
        else:
            time.sleep(1)

    def search_subreddit(self, subreddit, query, after=None):
        """Search a subreddit with a query."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT
        }

        params = {
            "q": query,
            "limit": 100,
            "sort": "top",  # Top posts more likely to be funny
            "t": "all",
            "restrict_sr": "true",
        }
        if after:
            params["after"] = after

        response = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/search",
            headers=headers,
            params=params
        )

        if response.status_code == 429:
            print(f"  [429] Rate limited, waiting 60s...")
            time.sleep(60)
            return self.search_subreddit(subreddit, query, after)

        if response.status_code != 200:
            print(f"  [ERROR] API returned {response.status_code}: {response.text[:100]}")
            return {"data": {"children": [], "after": None}}

        self.handle_rate_limit(response)
        return response.json()

    def get_existing_posts(self, subreddit):
        """Get set of post IDs already saved."""
        folder = DATA_DIR / subreddit
        if not folder.exists():
            return set()
        return {f.stem for f in folder.glob("*.json") if not f.stem.endswith("_comments")}

    def save_post(self, subreddit, post_data, keyword_category):
        """Save post data as JSON file with metadata."""
        folder = DATA_DIR / subreddit
        folder.mkdir(parents=True, exist_ok=True)

        post_id = post_data["id"]
        filepath = folder / f"{post_id}.json"

        post_data["_search_metadata"] = {
            "found_via": "jokes_keyword_search",
            "keyword_category": keyword_category,
            "search_date": datetime.now().isoformat(),
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)

    def search_with_keywords(self, subreddit, category, keywords):
        """Search subreddit with a list of keywords."""
        existing = self.get_existing_posts(subreddit)
        total_new = 0
        total_skipped = 0

        for keyword in keywords:
            print(f"    Searching: \"{keyword}\"")

            after = None
            pages = 0
            max_pages = 3

            while pages < max_pages:
                pages += 1
                data = self.search_subreddit(subreddit, keyword, after)
                posts = data.get("data", {}).get("children", [])
                after = data.get("data", {}).get("after")

                if not posts:
                    break

                new_count = 0
                for post in posts:
                    post_data = post["data"]
                    post_id = post_data["id"]

                    if post_id in existing:
                        total_skipped += 1
                    else:
                        self.save_post(subreddit, post_data, category)
                        existing.add(post_id)
                        total_new += 1
                        new_count += 1

                if new_count > 0:
                    print(f"      Page {pages}: +{new_count} new posts")

                if not after:
                    break

        return total_new, total_skipped

    def run(self):
        """Run keyword search across all subreddits."""
        print("=" * 70)
        print("REDDIT KEYWORD SEARCH - Flipping Jokes & Memes")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        self.get_token()

        total_keywords = sum(len(kws) for kws in KEYWORDS.values())
        print(f"\nKeyword categories: {len(KEYWORDS)}")
        print(f"Total keywords: {total_keywords}")
        print(f"Target subreddits: {len(SUBREDDITS)}")
        print(f"Estimated searches: {total_keywords * len(SUBREDDITS)}")

        results = {}
        grand_total_new = 0
        grand_total_skipped = 0

        for subreddit in SUBREDDITS:
            print(f"\n{'='*70}")
            print(f"SUBREDDIT: r/{subreddit}")
            print(f"{'='*70}")

            sub_new = 0
            sub_skipped = 0

            for category, keywords in KEYWORDS.items():
                print(f"\n  Category: {category} ({len(keywords)} keywords)")
                new, skipped = self.search_with_keywords(subreddit, category, keywords)
                sub_new += new
                sub_skipped += skipped
                print(f"  Category total: +{new} new, {skipped} skipped")

            results[subreddit] = {"new": sub_new, "skipped": sub_skipped}
            grand_total_new += sub_new
            grand_total_skipped += sub_skipped

            print(f"\n  Subreddit total: +{sub_new} new, {sub_skipped} skipped")
            print(f"  API requests made: {self.request_count}")

        # Final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)

        for sub, stats in results.items():
            print(f"  r/{sub}: +{stats['new']} new, {stats['skipped']} skipped")

        print(f"\nGRAND TOTAL: {grand_total_new} new posts saved, {grand_total_skipped} skipped")
        print(f"Total API requests: {self.request_count}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    searcher = RedditJokesSearcher()
    searcher.run()

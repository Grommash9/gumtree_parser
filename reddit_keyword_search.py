#!/usr/bin/env python3
"""
Reddit Keyword Search Script
One-off script to find posts about sourcing vintage furniture and jewelry
in the UK for flipping/reselling.
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

# Target subreddits for UK flipping/vintage sourcing
SUBREDDITS = [
    "FlippingUK",
    "eBaySellerAdvice",
    "Flipping",
    "Antiques",
    "vintage",
    "Mid_Century",
    "AskUK",
    "UKPersonalFinance",
    "Etsy",
    "ThriftStoreHauls",
    "FurnitureRestoration",
    "upcycling",
    "CasualUK",
]

# Keywords organized by theme
KEYWORDS = {
    # Sourcing locations UK
    "sourcing_locations_uk": [
        "charity shops UK",
        "car boot sale",
        "car boot finds",
        "boot sale UK",
        "house clearance UK",
        "estate sale UK",
        "auction house UK",
        "antique fair UK",
        "flea market UK",
        "facebook marketplace finds",
        "gumtree finds",
        "preloved UK",
        "British Heart Foundation furniture",
        "Emmaus furniture",
        "tip shop UK",
        "recycling centre finds",
    ],

    # Vintage furniture specific
    "vintage_furniture": [
        "vintage furniture flip",
        "mid century furniture UK",
        "retro furniture sourcing",
        "ercol chairs",
        "G Plan furniture",
        "teak furniture UK",
        "danish furniture UK",
        "vintage sideboard",
        "antique furniture profit",
        "upcycle furniture sell",
        "restore furniture flip",
        "MCM furniture UK",
        "parker knoll",
        "ercol flipping",
        "nathan furniture",
    ],

    # Jewelry sourcing and flipping
    "jewelry_flipping": [
        "vintage jewelry UK",
        "antique jewelry flipping",
        "gold jewelry profit",
        "silver hallmarks UK",
        "costume jewelry resale",
        "estate jewelry UK",
        "jewelry lot flip",
        "scrap gold UK",
        "hallmark dating UK",
        "vintage brooch",
        "antique rings flip",
        "jewelry car boot",
        "charity shop jewelry",
        "9ct gold finds",
        "sterling silver finds",
    ],

    # Success stories and tips
    "flipping_success": [
        "best flip ever",
        "biggest profit flip",
        "flipping success story",
        "made profit on",
        "sold for profit",
        "great find today",
        "amazing flip",
        "what sold well",
        "best selling items",
        "quick flip",
        "easy money flipping",
        "side hustle flipping",
    ],

    # Practical tips
    "practical_tips": [
        "flipping tips UK",
        "beginner flipping",
        "how to start flipping",
        "what to look for",
        "best items to flip",
        "profit margin flipping",
        "shipping furniture UK",
        "collection only tips",
        "photography tips selling",
        "listing tips eBay",
    ],

    # Specific finds and hauls
    "finds_hauls": [
        "charity shop haul",
        "boot sale haul",
        "today's finds",
        "weekly haul",
        "thrift haul UK",
        "sourcing haul",
        "what I found",
        "look what I got",
        "scored today",
        "jackpot find",
    ],
}

DATA_DIR = Path(__file__).parent / "data"


class RedditKeywordSearcher:
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

        # Be conservative with rate limiting
        if self.rate_limit_remaining < 10:
            sleep_time = self.rate_limit_reset + 5
            print(f"\n  [RATE LIMIT] Only {self.rate_limit_remaining:.0f} remaining, sleeping {sleep_time:.0f}s...")
            time.sleep(sleep_time)
        elif self.rate_limit_remaining < 30:
            print(f"  [RATE LIMIT] {self.rate_limit_remaining:.0f} remaining, slowing down...")
            time.sleep(2)
        else:
            # Always add small delay between requests
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
            "sort": "relevance",
            "t": "all",  # All time
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
        return {f.stem for f in folder.glob("*.json")}

    def save_post(self, subreddit, post_data, keyword_category):
        """Save post data as JSON file with metadata."""
        folder = DATA_DIR / subreddit
        folder.mkdir(parents=True, exist_ok=True)

        post_id = post_data["id"]
        filepath = folder / f"{post_id}.json"

        # Add metadata about how we found this post
        post_data["_search_metadata"] = {
            "found_via": "keyword_search",
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
            max_pages = 3  # Limit pages per keyword to avoid too many requests

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
        print("REDDIT KEYWORD SEARCH - UK Vintage Furniture & Jewelry Flipping")
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
    searcher = RedditKeywordSearcher()
    searcher.run()

#!/usr/bin/env python3
"""
Reddit Keyword Search - FlipperHelper Competitive Intelligence
One-off script to find posts about reselling inventory/profit tracking tools,
workflow pain points, and competitor apps in the buy-at-market → sell-online space.
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

# Target subreddits for reselling/flipping communities
SUBREDDITS = [
    # Primary flipping/reselling
    "Flipping",
    "FlippingUK",
    "eBaySellers",
    "eBay",
    "eBaySellerAdvice",

    # Platform communities (where sellers discuss workflow)
    "poshmark",
    "Mercari",
    "depop",
    "Vinted",
    "Etsy",

    # Thrifting/sourcing
    "ThriftStoreHauls",
    "thrifting",

    # UK-specific
    "CasualUK",
    "UKPersonalFinance",

    # Side hustle
    "sidehustle",
    "smallbusiness",
]

# Keywords organized by theme — competitive intelligence for FlipperHelper
KEYWORDS = {
    # Tracking what you buy
    "purchase_tracking_pain": [
        "tracking inventory reselling", "track what I bought",
        "forgot what I paid", "tracking purchases flipping",
        "how do you track inventory", "keeping track of items",
        "spreadsheet inventory reselling", "inventory management reselling",
        "how do you organize inventory", "track cost of goods",
        "photo inventory system", "logging purchases reselling",
    ],

    # Knowing your real profit
    "profit_tracking": [
        "tracking profit flipping", "calculate profit reselling",
        "actual profit after expenses", "cost of goods sold reselling",
        "how much profit flipping", "is flipping worth it money",
        "net profit reselling", "profit per item tracking",
        "do you track every purchase", "flipping income tracking",
        "real profit after fees shipping", "profit loss spreadsheet reselling",
    ],

    # Entry fees, transport, hidden costs
    "expense_pain": [
        "entry fee car boot", "travel costs flipping",
        "petrol costs reselling", "gas money flipping",
        "expenses eating into profit", "hidden costs reselling",
        "mileage tracking reseller", "cost of going to markets",
        "how much spend on sourcing", "overhead costs flipping",
        "market entry fee worth it", "transport costs selling",
    ],

    # General workflow pain
    "workflow_frustrations": [
        "flipping too much work", "reselling time consuming",
        "hate spreadsheets reselling", "better way to track sales",
        "disorganized inventory", "losing track of items",
        "photographing items tedious", "bookkeeping nightmare reselling",
        "tax tracking reselling", "reselling burnout tracking",
        "streamline flipping process", "spending more time tracking than selling",
    ],

    # People looking for tools
    "app_tool_search": [
        "app to track reselling", "inventory app for flippers",
        "best app for reselling", "recommend reselling app",
        "app track what I sell", "simple inventory app selling",
        "want app track purchases sales", "looking for flipping tool",
        "wish there was an app flipping", "need app track profit",
        "offline inventory app", "free inventory app reselling",
        "no subscription inventory app", "app for small reseller",
    ],

    # People outgrowing spreadsheets
    "spreadsheet_problems": [
        "spreadsheet reselling", "google sheets inventory reselling",
        "excel inventory tracking selling", "outgrown spreadsheet reselling",
        "spreadsheet template reselling", "too many items for spreadsheet",
        "spreadsheet getting messy", "better than spreadsheet reselling",
        "spreadsheet profit tracker", "manual tracking reselling",
    ],

    # FlipperHelper's core market — car boot/charity workflow
    "car_boot_charity_workflow": [
        "car boot sale profit", "charity shop reselling profit",
        "car boot what sold", "boot sale haul sold",
        "tracking car boot purchases", "how much spend car boot",
        "charity shop flipping tips", "car boot to eBay workflow",
        "charity shop to Vinted", "sourcing to selling process",
        "buying to reselling workflow", "market to online selling",
        "flea market reselling process", "thrift to sell workflow",
    ],

    # What people use now — competitor tools
    "competitor_tools": [
        "eBay seller hub inventory", "seller tools review",
        "best free tool reselling", "paying for reselling tools",
        "reselling app review", "inventory app review reselling",
        "Sortly inventory", "airtable inventory reselling",
        "notion inventory reselling", "reselling tool expensive",
        "subscription fatigue reselling app", "what app do you use reselling",
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
        print("REDDIT KEYWORD SEARCH - FlipperHelper Competitive Intelligence")
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

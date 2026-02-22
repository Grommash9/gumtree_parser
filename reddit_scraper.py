#!/usr/bin/env python3
"""
Reddit Post Scraper
Collects latest posts from target subreddits and saves as JSON.
"""

import os
import json
import time
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime
from pathlib import Path

# Configuration
CLIENT_ID = "equQMWfew9ak4nimpi2MBQ"
CLIENT_SECRET = "bwTnFcHekESh01FoAGBZoXqJVhNaSg"
USER_AGENT = "funnelboost-scraper/1.0"

SUBREDDITS = [
    "SharedOwnershipUK",
    "relationship_advice",
    "relationships",
    "relationships_advice",
    "sex",
    "UKPersonalFinance",
    "UKInvesting",
    "smallbusinessuk",
    "HousingUK",
    "FlippingUK",
    "eBaySellerAdvice",
    "wildcampingintheuk",

]

DATA_DIR = Path(__file__).parent / "data"


class RedditScraper:
    def __init__(self):
        self.access_token = None
        self.rate_limit_remaining = 1000
        self.rate_limit_reset = 600

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
        self.rate_limit_remaining = float(response.headers.get('x-ratelimit-remaining', 1000))
        self.rate_limit_reset = float(response.headers.get('x-ratelimit-reset', 600))

        if self.rate_limit_remaining < 10:
            sleep_time = self.rate_limit_reset + 1
            print(f"\n  Rate limit low ({self.rate_limit_remaining}), sleeping {sleep_time:.0f}s...")
            time.sleep(sleep_time)
        elif self.rate_limit_remaining < 50:
            time.sleep(0.5)

    def fetch_posts(self, subreddit, after=None):
        """Fetch a page of posts from subreddit."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT
        }

        params = {"limit": 100}
        if after:
            params["after"] = after

        response = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/new",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text[:200]}")

        self.handle_rate_limit(response)
        return response.json()

    def get_existing_posts(self, subreddit):
        """Get set of post IDs already saved."""
        folder = DATA_DIR / subreddit
        if not folder.exists():
            return set()
        return {f.stem for f in folder.glob("*.json")}

    def save_post(self, subreddit, post_data):
        """Save post data as JSON file."""
        folder = DATA_DIR / subreddit
        folder.mkdir(parents=True, exist_ok=True)

        post_id = post_data["id"]
        filepath = folder / f"{post_id}.json"

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(post_data, f, indent=2, ensure_ascii=False)

    def scrape_subreddit(self, subreddit):
        """Scrape all available posts from a subreddit."""
        print(f"\n{'='*60}")
        print(f"Scraping r/{subreddit}")
        print(f"{'='*60}")

        existing = self.get_existing_posts(subreddit)
        print(f"Existing posts: {len(existing)}")

        after = None
        total_fetched = 0
        new_saved = 0
        skipped = 0
        page = 0

        while True:
            page += 1
            data = self.fetch_posts(subreddit, after)
            posts = data.get("data", {}).get("children", [])
            after = data.get("data", {}).get("after")

            if not posts:
                print(f"  Page {page}: No posts returned")
                break

            page_new = 0
            page_skipped = 0

            for post in posts:
                post_data = post["data"]
                post_id = post_data["id"]
                total_fetched += 1

                if post_id in existing:
                    skipped += 1
                    page_skipped += 1
                else:
                    self.save_post(subreddit, post_data)
                    existing.add(post_id)
                    new_saved += 1
                    page_new += 1

            # Show progress
            oldest_date = ""
            if posts:
                oldest = posts[-1]["data"]
                created = datetime.fromtimestamp(oldest.get("created_utc", 0))
                oldest_date = created.strftime("%Y-%m-%d %H:%M")

            print(f"  Page {page}: {len(posts)} posts | +{page_new} new, {page_skipped} existing | oldest: {oldest_date} | API: {self.rate_limit_remaining:.0f} left")

            if not after or not page_new:
                print(f"  End of pagination reached")
                break

        print(f"\nSubreddit complete:")
        print(f"  Total fetched: {total_fetched}")
        print(f"  New saved: {new_saved}")
        print(f"  Skipped (existing): {skipped}")

        return {"fetched": total_fetched, "new": new_saved, "skipped": skipped}

    def run(self):
        """Run scraper for all subreddits."""
        print("="*60)
        print("REDDIT POST SCRAPER")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Subreddits: {', '.join(SUBREDDITS)}")
        print("="*60)

        self.get_token()

        results = {}
        for subreddit in SUBREDDITS:
            results[subreddit] = self.scrape_subreddit(subreddit)

        # Final summary
        print("\n" + "="*60)
        print("FINAL SUMMARY")
        print("="*60)

        total_new = 0
        total_skipped = 0

        for sub, stats in results.items():
            print(f"  r/{sub}: {stats['new']} new, {stats['skipped']} skipped")
            total_new += stats['new']
            total_skipped += stats['skipped']

        print(f"\nTotal: {total_new} new posts saved, {total_skipped} skipped")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    scraper = RedditScraper()
    scraper.run()

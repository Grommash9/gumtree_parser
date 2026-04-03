#!/usr/bin/env python3
"""
Reddit Top & Hot Posts Scraper
Fetches top and hot posts from target subreddits for the last 90 days.
Designed to collect as many high-engagement posts as possible for content analysis.

Usage:
    # Scrape from discovered subreddits (after running reddit_subreddit_discovery.py)
    python reddit_top_posts_scraper.py

    # Or scrape specific subreddits
    python reddit_top_posts_scraper.py --subreddits FlippingUK Flipping SideHustle
"""

import json
import time
import argparse
import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, timezone
from pathlib import Path

# Configuration
CLIENT_ID = "equQMWfew9ak4nimpi2MBQ"
CLIENT_SECRET = "bwTnFcHekESh01FoAGBZoXqJVhNaSg"
USER_AGENT = "funnelboost-scraper/1.0"

DATA_DIR = Path(__file__).parent / "data"
DISCOVERY_DIR = DATA_DIR / "_subreddits"
TOP_POSTS_DIR = DATA_DIR / "_top_posts"

# How far back to look (seconds). 90 days = 7,776,000s
CUTOFF_DAYS = 90
CUTOFF_SECONDS = CUTOFF_DAYS * 86400

# Minimum subscribers to bother scraping
MIN_SUBSCRIBERS = 5000

# Reddit API sort types and time filters
# top: score-ranked. hot: trending now. rising: gaining momentum
SORT_MODES = [
    {"sort": "top", "t": "year"},      # Top posts this year (captures last 90 days + more)
    {"sort": "top", "t": "month"},     # Top posts this month (more focused)
    {"sort": "hot", "t": None},        # Currently trending
    {"sort": "top", "t": "all"},       # All-time top (for understanding what really works)
]

# Max pages per sort mode per subreddit (100 posts/page)
MAX_PAGES_PER_MODE = 10


class TopPostsScraper:
    def __init__(self):
        self.access_token = None
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 600
        self.request_count = 0
        self.all_posts = {}  # post_id -> post_data (deduped across modes)

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
        self.access_token = data["access_token"]
        print(f"Token acquired (expires in {data.get('expires_in', '?')}s)")

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": USER_AGENT
        }

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
            time.sleep(2)
        else:
            time.sleep(0.5)

    def fetch_posts(self, subreddit, sort, t=None, after=None):
        """Fetch posts from a subreddit with given sort mode."""
        params = {"limit": 100}
        if t:
            params["t"] = t
        if after:
            params["after"] = after

        url = f"https://oauth.reddit.com/r/{subreddit}/{sort}"
        response = requests.get(url, headers=self._headers(), params=params)

        if response.status_code == 429:
            print(f"  [429] Rate limited, waiting 60s...")
            time.sleep(60)
            return self.fetch_posts(subreddit, sort, t, after)

        if response.status_code == 403:
            print(f"  [403] r/{subreddit} is private or quarantined, skipping")
            return {"data": {"children": [], "after": None}}

        if response.status_code != 200:
            print(f"  [ERROR] {response.status_code}: {response.text[:100]}")
            return {"data": {"children": [], "after": None}}

        self.handle_rate_limit(response)
        return response.json()

    def fetch_comments(self, subreddit, post_id):
        """Fetch top comments for a post."""
        response = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/comments/{post_id}",
            headers=self._headers(),
            params={"limit": 50, "depth": 3, "sort": "top"}
        )

        if response.status_code != 200:
            return []

        self.handle_rate_limit(response)

        # Reddit returns [post_listing, comments_listing]
        data = response.json()
        if len(data) < 2:
            return []

        comments = []
        for child in data[1].get("data", {}).get("children", []):
            if child.get("kind") != "t1":
                continue
            c = child["data"]
            comments.append({
                "id": c.get("id"),
                "author": c.get("author"),
                "body": c.get("body", "")[:2000],
                "score": c.get("score", 0),
                "created_utc": c.get("created_utc"),
            })

        return comments

    def scrape_subreddit(self, subreddit):
        """Scrape top/hot posts from a single subreddit."""
        print(f"\n{'='*60}")
        print(f"r/{subreddit}")
        print(f"{'='*60}")

        cutoff_utc = time.time() - CUTOFF_SECONDS
        sub_posts = {}  # post_id -> post_data for this subreddit

        for mode in SORT_MODES:
            sort = mode["sort"]
            t = mode.get("t")
            label = f"{sort}/{t}" if t else sort

            print(f"\n  Mode: {label}")

            after = None
            pages = 0
            mode_new = 0
            mode_old = 0

            while pages < MAX_PAGES_PER_MODE:
                pages += 1
                data = self.fetch_posts(subreddit, sort, t, after)
                posts = data.get("data", {}).get("children", [])
                after = data.get("data", {}).get("after")

                if not posts:
                    break

                page_new = 0
                for post in posts:
                    pd = post["data"]
                    post_id = pd.get("id")
                    created_utc = pd.get("created_utc", 0)

                    # For top/all we still collect but flag as outside window
                    in_window = created_utc >= cutoff_utc

                    if post_id not in sub_posts:
                        sub_posts[post_id] = {
                            "post_id": post_id,
                            "subreddit": pd.get("subreddit", subreddit),
                            "title": pd.get("title", ""),
                            "selftext": pd.get("selftext", "")[:5000],
                            "author": pd.get("author", ""),
                            "created_utc": created_utc,
                            "created_date": datetime.fromtimestamp(created_utc, tz=timezone.utc).strftime("%Y-%m-%d") if created_utc else None,
                            "score": pd.get("score", 0),
                            "upvote_ratio": pd.get("upvote_ratio", 0),
                            "num_comments": pd.get("num_comments", 0),
                            "permalink": pd.get("permalink", ""),
                            "url": pd.get("url", ""),
                            "link_flair_text": pd.get("link_flair_text"),
                            "over_18": pd.get("over_18", False),
                            "is_self": pd.get("is_self", True),
                            "in_90d_window": in_window,
                            "_found_via": [label],
                        }
                        page_new += 1
                        mode_new += 1
                    else:
                        # Track which modes found it
                        if label not in sub_posts[post_id]["_found_via"]:
                            sub_posts[post_id]["_found_via"].append(label)

                    if not in_window:
                        mode_old += 1

                # Show progress
                oldest = posts[-1]["data"]
                oldest_date = datetime.fromtimestamp(oldest.get("created_utc", 0), tz=timezone.utc).strftime("%Y-%m-%d")
                print(f"    Page {pages}: {len(posts)} posts | +{page_new} new | oldest: {oldest_date} | API: {self.rate_limit_remaining:.0f}")

                if not after:
                    break

            print(f"    Mode total: {mode_new} unique posts ({mode_old} outside 90d)")

        # Now fetch comments for top posts (by score, limit to top 50 to save API calls)
        top_posts = sorted(sub_posts.values(), key=lambda x: x["score"], reverse=True)
        comment_count = min(50, len(top_posts))

        if comment_count > 0:
            print(f"\n  Fetching comments for top {comment_count} posts...")

        for i, post in enumerate(top_posts[:comment_count]):
            comments = self.fetch_comments(subreddit, post["post_id"])
            post["_top_comments"] = comments
            if (i + 1) % 10 == 0:
                print(f"    {i+1}/{comment_count} done | API: {self.rate_limit_remaining:.0f}")

        # Save
        self._save_subreddit(subreddit, sub_posts)

        # Stats
        in_window = sum(1 for p in sub_posts.values() if p.get("in_90d_window"))
        all_time = len(sub_posts) - in_window
        top_score = max((p["score"] for p in sub_posts.values()), default=0)
        print(f"\n  TOTAL: {len(sub_posts)} posts ({in_window} in 90d, {all_time} older) | top score: {top_score}")

        return len(sub_posts)

    def _save_subreddit(self, subreddit, posts):
        """Save all posts for a subreddit."""
        out_dir = TOP_POSTS_DIR / subreddit
        out_dir.mkdir(parents=True, exist_ok=True)

        # Save individual posts
        for post_id, post_data in posts.items():
            filepath = out_dir / f"{post_id}.json"
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(post_data, f, indent=2, ensure_ascii=False)

        # Save summary sorted by score
        summary = sorted(posts.values(), key=lambda x: x["score"], reverse=True)
        summary_data = []
        for p in summary:
            summary_data.append({
                "post_id": p["post_id"],
                "title": p["title"][:120],
                "score": p["score"],
                "num_comments": p["num_comments"],
                "upvote_ratio": p["upvote_ratio"],
                "created_date": p.get("created_date"),
                "in_90d": p.get("in_90d_window", False),
                "flair": p.get("link_flair_text"),
                "is_self": p.get("is_self"),
                "author": p["author"],
            })

        filepath = out_dir / "_summary.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, indent=2, ensure_ascii=False)

    def get_target_subreddits(self, cli_subreddits=None):
        """Get list of subreddits to scrape."""
        if cli_subreddits:
            return cli_subreddits

        # Try to load from discovery results
        summary_file = DISCOVERY_DIR / "subreddits_summary.json"
        if summary_file.exists():
            with open(summary_file) as f:
                subs = json.load(f)
            # Filter by subscriber count, skip NSFW
            targets = [
                s["name"] for s in subs
                if s.get("subscribers", 0) >= MIN_SUBSCRIBERS
                and not s.get("over18", False)
            ]
            print(f"Loaded {len(targets)} subreddits from discovery (>={MIN_SUBSCRIBERS:,} subscribers)")
            return targets

        # Fallback: hardcoded list of known relevant subreddits
        print("No discovery data found, using hardcoded list")
        return [
            "FlippingUK", "Flipping", "eBaySellerAdvice", "ThriftStoreHauls",
            "thrifting", "Etsy", "Vinted", "Depop", "poshmark", "Mercari",
            "FlippingInCanada", "SideHustle", "SideProject",
            "smallbusinessuk", "UKPersonalFinance",
            "Entrepreneur", "sweatystartup", "juststart",
            "GardenSaleFinds", "Reselling",
        ]

    def run(self, cli_subreddits=None):
        """Run top posts scraper."""
        print("=" * 70)
        print("REDDIT TOP & HOT POSTS SCRAPER")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Window: last {CUTOFF_DAYS} days + all-time top")
        print(f"Sort modes: {len(SORT_MODES)} ({', '.join(m['sort']+'/'+str(m.get('t','')) for m in SORT_MODES)})")
        print("=" * 70)

        self.get_token()

        targets = self.get_target_subreddits(cli_subreddits)
        print(f"\nTarget subreddits: {len(targets)}")
        for t in targets:
            print(f"  - r/{t}")

        results = {}
        for subreddit in targets:
            try:
                count = self.scrape_subreddit(subreddit)
                results[subreddit] = count
            except Exception as e:
                print(f"\n  [ERROR] r/{subreddit}: {e}")
                results[subreddit] = 0

        # Final summary
        print("\n" + "=" * 70)
        print("FINAL SUMMARY")
        print("=" * 70)

        total = 0
        for sub, count in sorted(results.items(), key=lambda x: x[1], reverse=True):
            print(f"  r/{sub:30s} {count:>6} posts")
            total += count

        print(f"\nTotal: {total} posts across {len(results)} subreddits")
        print(f"Total API requests: {self.request_count}")
        print(f"Data saved to: {TOP_POSTS_DIR}/")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape top & hot Reddit posts")
    parser.add_argument("--subreddits", nargs="+", help="Specific subreddits to scrape")
    args = parser.parse_args()

    scraper = TopPostsScraper()
    scraper.run(cli_subreddits=args.subreddits)

#!/usr/bin/env python3
"""
Reddit Comments Parser
Fetches comments for existing posts and saves them as separate JSON files.
"""

import json
import time
import requests
from requests.auth import HTTPBasicAuth
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from datetime import datetime
from pathlib import Path

# Configuration (same as main scraper)
CLIENT_ID = "equQMWfew9ak4nimpi2MBQ"
CLIENT_SECRET = "bwTnFcHekESh01FoAGBZoXqJVhNaSg"
USER_AGENT = "funnelboost-scraper/1.0"

DATA_DIR = Path(__file__).parent / "data"


class RedditCommentsParser:
    def __init__(self):
        self.access_token = None
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 600
        self.request_count = 0
        self.start_time = None

        # Create persistent session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False  # Don't raise, let us handle status codes
        )
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({"User-Agent": USER_AGENT})

    def get_token(self):
        """Get OAuth access token."""
        print("Getting OAuth token...")
        auth = HTTPBasicAuth(CLIENT_ID, CLIENT_SECRET)
        response = self.session.post(
            "https://www.reddit.com/api/v1/access_token",
            auth=auth,
            data={"grant_type": "client_credentials"}
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

    def get_posts_without_comments(self):
        """Scan data directory and find posts that don't have comments files."""
        posts_to_process = []
        total_posts = 0
        already_processed = 0

        if not DATA_DIR.exists():
            print(f"Data directory not found: {DATA_DIR}")
            return []

        for subreddit_dir in sorted(DATA_DIR.iterdir()):
            if not subreddit_dir.is_dir() or subreddit_dir.name.startswith('.'):
                continue

            subreddit_name = subreddit_dir.name

            for post_file in subreddit_dir.glob("*.json"):
                # Skip comments files
                if post_file.stem.endswith("_comments"):
                    continue

                total_posts += 1
                post_id = post_file.stem
                comments_file = subreddit_dir / f"{post_id}_comments.json"

                if comments_file.exists():
                    already_processed += 1
                else:
                    posts_to_process.append({
                        "subreddit": subreddit_name,
                        "post_id": post_id,
                        "post_file": post_file
                    })

        return posts_to_process, total_posts, already_processed

    def fetch_comments(self, subreddit, post_id):
        """Fetch all comments for a post."""
        headers = {
            "Authorization": f"Bearer {self.access_token}"
        }

        response = self.session.get(
            f"https://oauth.reddit.com/r/{subreddit}/comments/{post_id}",
            headers=headers,
            params={"limit": 500, "depth": 10}
        )

        if response.status_code == 429:
            print(f"  [429] Rate limited, waiting 60s...")
            time.sleep(60)
            return self.fetch_comments(subreddit, post_id)

        if response.status_code == 404:
            return {"error": "post_not_found", "comments": []}

        if response.status_code != 200:
            print(f"  [ERROR] API returned {response.status_code}: {response.text[:100]}")
            return {"error": f"api_error_{response.status_code}", "comments": []}

        self.handle_rate_limit(response)

        data = response.json()

        # Reddit returns [post_data, comments_data]
        if len(data) < 2:
            return {"error": "unexpected_response", "comments": []}

        comments_listing = data[1].get("data", {}).get("children", [])
        return {"comments": [c["data"] for c in comments_listing if c.get("kind") == "t1"]}

    def count_comments(self, comments):
        """Count total comments including nested replies."""
        count = 0
        for comment in comments:
            count += 1
            replies = comment.get("replies")
            if isinstance(replies, dict):
                nested = replies.get("data", {}).get("children", [])
                nested_comments = [c["data"] for c in nested if c.get("kind") == "t1"]
                count += self.count_comments(nested_comments)
        return count

    def save_comments(self, subreddit, post_id, comments_data):
        """Save comments to JSON file."""
        folder = DATA_DIR / subreddit
        filepath = folder / f"{post_id}_comments.json"

        output = {
            "post_id": post_id,
            "subreddit": subreddit,
            "fetched_at": datetime.now().isoformat(),
            "comment_count": self.count_comments(comments_data.get("comments", [])),
            "comments": comments_data.get("comments", []),
        }

        if "error" in comments_data:
            output["error"] = comments_data["error"]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    def format_time(self, seconds):
        """Format seconds into human readable time."""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            mins = seconds / 60
            return f"{mins:.0f}m"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            return f"{hours:.0f}h {mins:.0f}m"

    def estimate_completion(self, remaining_posts):
        """Estimate completion time based on current progress."""
        if self.request_count == 0 or self.start_time is None:
            # Assume 1 request per second
            return self.format_time(remaining_posts)

        elapsed = time.time() - self.start_time
        rate = self.request_count / elapsed  # requests per second
        if rate > 0:
            remaining_seconds = remaining_posts / rate
            return self.format_time(remaining_seconds)
        return "calculating..."

    def run(self):
        """Run the comments parser."""
        print("=" * 70)
        print("REDDIT COMMENTS PARSER")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 70)

        # Scan for posts without comments
        print("\nScanning data directory...")
        posts_to_process, total_posts, already_processed = self.get_posts_without_comments()

        print(f"\nTotal posts: {total_posts}")
        print(f"Already have comments: {already_processed}")
        print(f"Posts to process: {len(posts_to_process)}")

        if not posts_to_process:
            print("\nAll posts already have comments. Nothing to do.")
            return

        # Estimate time
        estimated_time = self.format_time(len(posts_to_process))
        print(f"Estimated time: {estimated_time} (at ~1 req/sec)")

        self.get_token()
        self.start_time = time.time()

        # Group posts by subreddit for better output
        current_subreddit = None
        subreddit_count = 0
        subreddit_total = 0

        for idx, post_info in enumerate(posts_to_process):
            subreddit = post_info["subreddit"]
            post_id = post_info["post_id"]

            # New subreddit header
            if subreddit != current_subreddit:
                if current_subreddit is not None:
                    print(f"\n  Subreddit complete: {subreddit_count} posts processed")

                # Count posts in this subreddit
                subreddit_total = sum(1 for p in posts_to_process[idx:] if p["subreddit"] == subreddit)
                subreddit_count = 0
                current_subreddit = subreddit

                print(f"\n{'=' * 70}")
                print(f"Processing r/{subreddit} ({subreddit_total} posts)")
                print(f"{'=' * 70}")

            subreddit_count += 1
            remaining = len(posts_to_process) - idx - 1
            eta = self.estimate_completion(remaining)

            # Fetch comments
            result = self.fetch_comments(subreddit, post_id)
            comment_count = self.count_comments(result.get("comments", []))

            # Save
            self.save_comments(subreddit, post_id, result)

            # Progress line
            error_str = f" [{result['error']}]" if "error" in result else ""
            print(f"  [{subreddit_count}/{subreddit_total}] {post_id} - {comment_count} comments{error_str} | ETA: {eta}")

        # Final summary
        print(f"\n  Subreddit complete: {subreddit_count} posts processed")

        elapsed = time.time() - self.start_time
        print("\n" + "=" * 70)
        print("COMPLETE")
        print("=" * 70)
        print(f"Posts processed: {len(posts_to_process)}")
        print(f"API requests: {self.request_count}")
        print(f"Time elapsed: {self.format_time(elapsed)}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    parser = RedditCommentsParser()
    parser.run()

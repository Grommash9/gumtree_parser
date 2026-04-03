#!/usr/bin/env python3
"""
Reddit Subreddit Discovery
Search for subreddits by keywords, fetch their info and rules.
Saves results as JSON for analysis.
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

# Keywords to discover subreddits where our target audience hangs out
SEARCH_QUERIES = [
    # Reselling / flipping
    "reselling",
    "flipping items",
    "thrift flipping",
    "car boot sale",
    "flea market",
    "garage sale",
    "charity shop",
    "secondhand",
    "thrifting",
    # Platforms
    "ebay seller",
    "vinted",
    "depop",
    "poshmark",
    "mercari",
    "facebook marketplace selling",
    # Side hustle / business
    "side hustle",
    "small business",
    "extra income",
    "passive income",
    # Inventory / tracking
    "inventory management",
    "profit tracking",
    # Dev / indie communities (for app promotion)
    "side project",
    "indie hackers",
    "ios app",
    "show your app",
    "build in public",
    "startup",
    "entrepreneur",
    # UK specific
    "uk personal finance",
    "uk side hustle",
]

# Subreddits we already know about (skip during discovery but include in output)
KNOWN_SUBREDDITS = [
    "FlippingUK",
    "Flipping",
    "eBaySellerAdvice",
    "ThriftStoreHauls",
    "thrifting",
    "Etsy",
    "Vinted",
    "Depop",
    "poshmark",
    "Mercari",
    "FlippingInCanada",
    "SideHustle",
    "SideProject",
    "IndieHackers",
    "ShowYourApp",
    "buildinpublic",
    "juststart",
    "smallbusinessuk",
    "UKPersonalFinance",
    "Flipping",
    "flipperhelper",
]

DATA_DIR = Path(__file__).parent / "data" / "_subreddits"


class SubredditDiscovery:
    def __init__(self):
        self.access_token = None
        self.rate_limit_remaining = 100
        self.rate_limit_reset = 600
        self.request_count = 0
        self.discovered = {}  # name_lower -> subreddit_data

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

    def search_subreddits(self, query):
        """Search for subreddits matching a query."""
        response = requests.get(
            "https://oauth.reddit.com/subreddits/search",
            headers=self._headers(),
            params={
                "q": query,
                "limit": 25,
                "sort": "relevance",
            }
        )

        if response.status_code == 429:
            print(f"  [429] Rate limited, waiting 60s...")
            time.sleep(60)
            return self.search_subreddits(query)

        if response.status_code != 200:
            print(f"  [ERROR] {response.status_code}: {response.text[:100]}")
            return []

        self.handle_rate_limit(response)
        children = response.json().get("data", {}).get("children", [])
        return [c["data"] for c in children]

    def fetch_subreddit_about(self, subreddit):
        """Fetch subreddit about/description."""
        response = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/about",
            headers=self._headers(),
        )

        if response.status_code != 200:
            print(f"    [ERROR] about for r/{subreddit}: {response.status_code}")
            return None

        self.handle_rate_limit(response)
        return response.json().get("data", {})

    def fetch_subreddit_rules(self, subreddit):
        """Fetch subreddit rules."""
        response = requests.get(
            f"https://oauth.reddit.com/r/{subreddit}/about/rules",
            headers=self._headers(),
        )

        if response.status_code != 200:
            print(f"    [ERROR] rules for r/{subreddit}: {response.status_code}")
            return []

        self.handle_rate_limit(response)
        return response.json().get("rules", [])

    def save_results(self):
        """Save all discovered subreddits to JSON."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Save full data
        filepath = DATA_DIR / "all_subreddits.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.discovered, f, indent=2, ensure_ascii=False)

        # Save summary sorted by subscribers
        summary = []
        for name, data in self.discovered.items():
            summary.append({
                "name": data.get("display_name", name),
                "subscribers": data.get("subscribers", 0),
                "active_users": data.get("active_user_count", 0),
                "description": (data.get("public_description", "") or "")[:200],
                "over18": data.get("over18", False),
                "rules_count": len(data.get("_rules", [])),
                "self_promo_rule": data.get("_self_promo_rule", None),
                "discovered_via": data.get("_discovered_via", []),
            })

        summary.sort(key=lambda x: x["subscribers"], reverse=True)

        filepath = DATA_DIR / "subreddits_summary.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        print(f"\nSaved {len(self.discovered)} subreddits to {DATA_DIR}/")

    def run(self):
        """Run subreddit discovery."""
        print("=" * 70)
        print("REDDIT SUBREDDIT DISCOVERY")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Search queries: {len(SEARCH_QUERIES)}")
        print("=" * 70)

        self.get_token()

        # Phase 1: Search for subreddits by keyword
        print("\n--- Phase 1: Keyword search ---")
        for query in SEARCH_QUERIES:
            print(f"\n  Searching: \"{query}\"")
            results = self.search_subreddits(query)

            new_count = 0
            for sub_data in results:
                name = sub_data.get("display_name", "")
                name_lower = name.lower()
                subscribers = sub_data.get("subscribers", 0)
                # Skip tiny subreddits

                if subscribers is None or subscribers < 1000:
                    continue

                if name_lower not in self.discovered:
                    sub_data["_discovered_via"] = [query]
                    self.discovered[name_lower] = sub_data
                    new_count += 1
                else:
                    # Track which queries found it
                    existing = self.discovered[name_lower].get("_discovered_via", [])
                    if query not in existing:
                        existing.append(query)
                        self.discovered[name_lower]["_discovered_via"] = existing

            print(f"    Found {len(results)} subs, {new_count} new (>1k subscribers)")

        # Add known subreddits that might not show up in search
        for name in KNOWN_SUBREDDITS:
            name_lower = name.lower()
            if name_lower not in self.discovered:
                self.discovered[name_lower] = {
                    "display_name": name,
                    "_discovered_via": ["known_list"],
                }

        print(f"\nTotal discovered: {len(self.discovered)} subreddits")

        # Phase 2: Fetch about + rules for each subreddit
        print("\n--- Phase 2: Fetching about & rules ---")
        for name_lower, data in self.discovered.items():
            display_name = data.get("display_name", name_lower)
            print(f"  r/{display_name}...", end=" ", flush=True)

            # Fetch about if we don't have subscriber count (known_list items)
            if "subscribers" not in data:
                about = self.fetch_subreddit_about(display_name)
                if about:
                    data.update(about)
                    print(f"{data.get('subscribers', '?')} subs", end=" ")
                else:
                    print("(about failed)", end=" ")

            # Fetch rules
            rules = self.fetch_subreddit_rules(display_name)
            data["_rules"] = [
                {
                    "short_name": r.get("short_name") or "",
                    "description": r.get("description") or "",
                    "kind": r.get("kind") or "",
                }
                for r in rules
            ]

            # Check for self-promotion rules
            self_promo_rule = None
            for rule in rules:
                short = rule.get("short_name") or ""
                desc = rule.get("description") or ""
                name_check = (short + " " + desc).lower()
                if any(kw in name_check for kw in ["self-promot", "self promot", "spam", "advertis", "promo"]):
                    self_promo_rule = short + ": " + desc[:200]
                    break

            data["_self_promo_rule"] = self_promo_rule
            print(f"| {len(rules)} rules | promo: {'YES' if self_promo_rule else 'no'}")

        self.save_results()

        # Print top subreddits by size
        print("\n" + "=" * 70)
        print("TOP SUBREDDITS BY SIZE")
        print("=" * 70)

        sorted_subs = sorted(
            self.discovered.values(),
            key=lambda x: x.get("subscribers", 0),
            reverse=True
        )

        for sub in sorted_subs[:40]:
            name = sub.get("display_name", "?")
            subs = sub.get("subscribers", 0)
            promo = "PROMO RULE" if sub.get("_self_promo_rule") else ""
            print(f"  r/{name:30s} {subs:>10,} subs  {promo}")

        print(f"\nTotal API requests: {self.request_count}")
        print(f"Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    discovery = SubredditDiscovery()
    discovery.run()



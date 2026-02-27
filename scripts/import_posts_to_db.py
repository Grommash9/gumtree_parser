#!/usr/bin/env python3
"""
Import Reddit posts and comments from JSON files into PostgreSQL database.

Usage:
    python scripts/import_posts_to_db.py [subreddit] [--with-comments]

Examples:
    python scripts/import_posts_to_db.py                    # Import all subreddits
    python scripts/import_posts_to_db.py Antiques           # Import only Antiques
    python scripts/import_posts_to_db.py --with-comments    # Import posts + comments
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.config import DATA_DIR
from common.database import (
    bulk_insert_posts,
    bulk_insert_comments,
    get_existing_post_ids,
    get_post_stats,
    check_connection,
)


def load_post_file(filepath: Path) -> dict:
    """Load a single post JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"  Error loading {filepath}: {e}")
        return None


def load_comments_file(filepath: Path) -> dict:
    """Load a comments JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return None


def import_subreddit(subreddit_dir: Path, existing_ids: set, with_comments: bool = False) -> dict:
    """
    Import posts (and optionally comments) from a subreddit directory.
    Returns import statistics.
    """
    subreddit_name = subreddit_dir.name
    stats = {
        'subreddit': subreddit_name,
        'posts_found': 0,
        'posts_new': 0,
        'posts_imported': 0,
        'comments_imported': 0,
        'errors': 0
    }

    # Find all post files (not comments)
    post_files = [f for f in subreddit_dir.glob("*.json")
                  if not f.stem.endswith("_comments")]

    stats['posts_found'] = len(post_files)

    # Filter to new posts only
    new_posts = []
    for pf in post_files:
        post_id = pf.stem
        if post_id not in existing_ids:
            post_data = load_post_file(pf)
            if post_data:
                new_posts.append(post_data)
            else:
                stats['errors'] += 1

    stats['posts_new'] = len(new_posts)

    # Import posts in batches
    if new_posts:
        try:
            imported = bulk_insert_posts(new_posts)
            stats['posts_imported'] = imported
        except Exception as e:
            print(f"  Error importing posts: {e}")
            stats['errors'] += len(new_posts)

    # Import comments if requested
    if with_comments:
        for post_file in post_files:
            post_id = post_file.stem
            comments_file = subreddit_dir / f"{post_id}_comments.json"

            if comments_file.exists():
                comments_data = load_comments_file(comments_file)
                if comments_data and 'comments' in comments_data:
                    try:
                        count = bulk_insert_comments(
                            comments_data['comments'],
                            post_id
                        )
                        stats['comments_imported'] += count
                    except Exception as e:
                        # Post might not exist in DB yet
                        pass

    return stats


def main():
    parser = argparse.ArgumentParser(description='Import Reddit posts to database')
    parser.add_argument('subreddit', nargs='?', help='Specific subreddit to import (optional)')
    parser.add_argument('--with-comments', action='store_true', help='Also import comments')
    parser.add_argument('--data-dir', default=DATA_DIR, help='Data directory path')
    args = parser.parse_args()

    data_path = Path(args.data_dir)

    print("=" * 70)
    print("REDDIT DATA IMPORTER")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Check database connection
    print("\nChecking database connection...")
    if not check_connection():
        print("ERROR: Cannot connect to database. Check your .env configuration.")
        sys.exit(1)
    print("Database connection OK")

    # Get existing post IDs to avoid duplicates
    print("Loading existing post IDs...")
    existing_ids = get_existing_post_ids()
    print(f"Found {len(existing_ids)} existing posts in database")

    # Find subreddit directories
    if args.subreddit:
        subreddit_dirs = [data_path / args.subreddit]
        if not subreddit_dirs[0].exists():
            print(f"ERROR: Subreddit directory not found: {subreddit_dirs[0]}")
            sys.exit(1)
    else:
        subreddit_dirs = sorted([
            d for d in data_path.iterdir()
            if d.is_dir() and not d.name.startswith('.')
        ])

    print(f"\nFound {len(subreddit_dirs)} subreddit(s) to import")
    if args.with_comments:
        print("Comments import: ENABLED")

    # Import each subreddit
    total_stats = {
        'posts_found': 0,
        'posts_new': 0,
        'posts_imported': 0,
        'comments_imported': 0,
        'errors': 0
    }

    for subreddit_dir in subreddit_dirs:
        print(f"\n--- r/{subreddit_dir.name} ---")

        stats = import_subreddit(subreddit_dir, existing_ids, args.with_comments)

        print(f"  Posts found: {stats['posts_found']}")
        print(f"  New posts: {stats['posts_new']}")
        print(f"  Imported: {stats['posts_imported']}")
        if args.with_comments:
            print(f"  Comments: {stats['comments_imported']}")
        if stats['errors']:
            print(f"  Errors: {stats['errors']}")

        # Update totals
        for key in total_stats:
            total_stats[key] += stats.get(key, 0)

        # Add newly imported IDs to existing set
        existing_ids.update(p.get('id') for p in [])  # Would need to track

    # Summary
    print("\n" + "=" * 70)
    print("IMPORT COMPLETE")
    print("=" * 70)
    print(f"Total posts found: {total_stats['posts_found']}")
    print(f"Total new posts: {total_stats['posts_new']}")
    print(f"Total imported: {total_stats['posts_imported']}")
    if args.with_comments:
        print(f"Total comments: {total_stats['comments_imported']}")
    if total_stats['errors']:
        print(f"Total errors: {total_stats['errors']}")

    # Show current database stats
    print("\nDatabase post counts by subreddit:")
    for subreddit, count in get_post_stats().items():
        print(f"  r/{subreddit}: {count}")


if __name__ == "__main__":
    main()

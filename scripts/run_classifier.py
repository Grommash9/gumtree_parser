#!/usr/bin/env python3
"""
Run Reddit post/comment classification.

Usage:
    python scripts/run_classifier.py <classifier_type> [options]

Examples:
    python scripts/run_classifier.py vintage --limit 100
    python scripts/run_classifier.py sex --post abc123
    python scripts/run_classifier.py housing --batch-size 50
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.database import (
    check_connection,
    check_tables_exist,
    get_classification_stats,
    get_classifier_subreddits,
)
from llm_classifier.azure_client import check_azure_connection
from llm_classifier.rate_limiter import rate_limiter
from llm_classifier.vintage.classifier import VintageClassifier
from llm_classifier.sex.classifier import SexClassifier
from llm_classifier.housing.classifier import HousingClassifier
from llm_classifier.flipping.classifier import FlippingClassifier


CLASSIFIERS = {
    'vintage': VintageClassifier,
    'sex': SexClassifier,
    'housing': HousingClassifier,
    'flipping': FlippingClassifier,
}


def main():
    parser = argparse.ArgumentParser(description='Run Reddit post classification')
    parser.add_argument('classifier', choices=list(CLASSIFIERS.keys()),
                        help='Classifier type to run')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum posts to process (default: all)')
    parser.add_argument('--post', type=str,
                        help='Process a single post by ID')
    parser.add_argument('--stats-only', action='store_true',
                        help='Only show statistics, don\'t process')
    args = parser.parse_args()

    print("=" * 70)
    print(f"REDDIT CLASSIFIER: {args.classifier.upper()}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Check database connection
    print("\nChecking database connection...")
    if not check_connection():
        print("ERROR: Cannot connect to database. Check your .env configuration.")
        sys.exit(1)
    print("Database connection OK")

    # Check tables exist
    tables = check_tables_exist()
    missing = [t for t, exists in tables.items() if not exists]
    if missing:
        print(f"ERROR: Missing tables: {missing}")
        print("Run: psql -d reddit_research -f scripts/init_db.sql")
        sys.exit(1)
    print("All required tables exist")

    # Check classifier subreddits are configured
    subreddits = get_classifier_subreddits(args.classifier)
    if not subreddits:
        print(f"\nWARNING: No subreddits configured for '{args.classifier}' classifier")
        print("Configure subreddits in the database:")
        print(f"  INSERT INTO subreddit_classifiers (subreddit, classifier_type)")
        print(f"  VALUES ('SubredditName', '{args.classifier}');")
        if not args.post:  # Only exit if not processing a specific post
            sys.exit(1)
    else:
        print(f"\nConfigured subreddits for {args.classifier}:")
        for sub in subreddits:
            print(f"  - r/{sub}")

    # Show current stats
    try:
        stats = get_classification_stats(args.classifier)
        print(f"\nClassification progress:")
        print(f"  Total posts: {stats['total']}")
        print(f"  Processed: {stats['processed']}")
        print(f"  Remaining: {stats['remaining']}")
        print(f"  Progress: {stats['progress_pct']:.1f}%")
    except Exception as e:
        print(f"Could not get stats: {e}")

    if args.stats_only:
        return

    # Check Azure connection
    print("\nChecking Azure OpenAI connection...")
    if not check_azure_connection():
        print("ERROR: Cannot connect to Azure OpenAI. Check your .env configuration.")
        sys.exit(1)

    # Initialize classifier
    classifier_class = CLASSIFIERS[args.classifier]
    classifier = classifier_class()

    # Process single post or batch
    if args.post:
        print(f"\nProcessing single post: {args.post}")
        result = classifier.classify_post(args.post)

        print(f"\nResult:")
        print(f"  Post ID: {result.get('post_id')}")
        print(f"  Relevant: {result.get('is_relevant')}")
        print(f"  Items extracted: {len(result.get('results', []))}")

        if result.get('results'):
            print(f"\nExtracted items:")
            for i, item in enumerate(result['results'], 1):
                print(f"  {i}. {item}")

    else:
        limit_str = str(args.limit) if args.limit else "all"
        print(f"\nProcessing batch (limit: {limit_str})...")
        results = classifier.process_batch(limit=args.limit)

        print(f"\nBatch results:")
        print(f"  Total processed: {results['processed']}/{results['total']}")
        print(f"  Relevant posts: {results['relevant']}")
        print(f"  Items extracted: {results['items_extracted']}")
        print(f"  Errors: {results['errors']}")

    # Show rate limiter stats
    rl_stats = rate_limiter.get_stats()
    print(f"\nRate limiter stats:")
    print(f"  Total requests: {rl_stats['total_requests']}")
    print(f"  Total tokens: {rl_stats['total_tokens']:,}")
    print(f"  Throttle events: {rl_stats['throttle_events']}")
    print(f"  Current TPM: {rl_stats['current_tpm']:,} / {rl_stats['tpm_limit']:,}")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

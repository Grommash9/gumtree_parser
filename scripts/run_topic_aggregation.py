#!/usr/bin/env python3
"""
Run topic aggregation on extracted flipping feedback items.

Usage:
    python scripts/run_topic_aggregation.py [--limit N]

Examples:
    python scripts/run_topic_aggregation.py --limit 50   # test with 50 items per type
    python scripts/run_topic_aggregation.py               # process all items
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.database import check_connection, get_feedback_items_for_aggregation
from llm_classifier.azure_client import check_azure_connection
from llm_classifier.flipping.aggregator import TopicAggregator


def main():
    parser = argparse.ArgumentParser(description='Run topic aggregation on flipping feedback')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max items per feedback type (for testing)')
    args = parser.parse_args()

    print("=" * 70)
    print("FLIPPING FEEDBACK - TOPIC AGGREGATION")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.limit:
        print(f"Limit: {args.limit} items per type")
    print("=" * 70)

    # Check database
    print("\nChecking database connection...")
    if not check_connection():
        print("ERROR: Cannot connect to database.")
        sys.exit(1)
    print("Database connection OK")

    # Check we have items to aggregate
    all_items = get_feedback_items_for_aggregation()
    if not all_items:
        print("\nNo feedback items found. Run the flipping classifier first:")
        print("  python scripts/run_classifier.py flipping --limit 100")
        sys.exit(1)

    print(f"\nFound {len(all_items)} feedback items to aggregate")

    # Count by type
    by_type = {}
    for item in all_items:
        ft = item['feedback_type']
        by_type[ft] = by_type.get(ft, 0) + 1
    for ft, count in sorted(by_type.items()):
        print(f"  {ft}: {count}")

    # Check Azure
    print("\nChecking Azure OpenAI connection...")
    if not check_azure_connection():
        print("ERROR: Cannot connect to Azure OpenAI.")
        sys.exit(1)

    # Run aggregation
    print("\nRunning topic aggregation...")
    aggregator = TopicAggregator()
    results = aggregator.run(limit_per_type=args.limit)

    print(f"\nAggregation complete:")
    print(f"  Run ID: {results['run_id']}")
    print(f"  Items processed: {results['items_processed']}")
    print(f"  Topics created: {results['topics_created']}")
    print(f"  Status: {results['status']}")

    print(f"\nFinished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()

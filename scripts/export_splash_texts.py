#!/usr/bin/env python3
"""
Export collected flipping jokes as a Swift splashTexts array.

Usage:
    python scripts/export_splash_texts.py [--min-confidence 0.8] [--format swift|json]

Outputs splash texts ready to paste into MoneyFlowView.swift.
"""

import sys
import json
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from common.database import get_cursor


def get_splash_texts(min_confidence: float = 0.7) -> list:
    """Get all splash texts above confidence threshold, deduplicated."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT DISTINCT ON (splash_text)
                splash_text, humor_category, source_type, confidence, author
            FROM flipping_jokes_items
            WHERE confidence >= %s
            ORDER BY splash_text, confidence DESC
        """, (min_confidence,))
        return list(cur.fetchall())


def format_swift(texts: list) -> str:
    """Format as a Swift array."""
    lines = ['private let splashTexts = [']
    for item in texts:
        escaped = item['splash_text'].replace('"', '\\"')
        lines.append(f'    "{escaped}",')
    lines.append(']')
    return '\n'.join(lines)


def format_json(texts: list) -> str:
    """Format as JSON array."""
    return json.dumps(
        [{'text': t['splash_text'], 'category': t['humor_category']} for t in texts],
        indent=2,
    )


def main():
    parser = argparse.ArgumentParser(description='Export splash texts')
    parser.add_argument('--min-confidence', type=float, default=0.7,
                        help='Minimum confidence threshold (default: 0.7)')
    parser.add_argument('--format', choices=['swift', 'json'], default='swift',
                        help='Output format (default: swift)')
    parser.add_argument('--category', type=str, default=None,
                        help='Filter by humor category')
    args = parser.parse_args()

    texts = get_splash_texts(min_confidence=args.min_confidence)

    if args.category:
        texts = [t for t in texts if t['humor_category'] == args.category]

    if not texts:
        print("No splash texts found. Run the flipping_jokes classifier first:")
        print("  python scripts/run_classifier.py flipping_jokes --limit 100")
        sys.exit(1)

    print(f"// Found {len(texts)} splash texts (min confidence: {args.min_confidence})")
    print(f"// Categories: {', '.join(sorted(set(t['humor_category'] for t in texts)))}")
    print()

    if args.format == 'swift':
        print(format_swift(texts))
    else:
        print(format_json(texts))


if __name__ == "__main__":
    main()

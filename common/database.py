"""
Centralized database access for Reddit Research project.
All components should use this module for PostgreSQL access.

Uses psycopg3 with connection pooling for thread-safe operations.
"""

import os
import atexit
from typing import List, Set, Dict, Any, Optional
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

# Load environment variables from .env file if present
# IMPORTANT: override=False ensures Docker environment variables take precedence
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
except ImportError:
    pass


# ============================================
# Configuration
# ============================================

def get_db_config() -> Dict[str, Any]:
    """Get database configuration from environment variables."""
    return {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'dbname': os.getenv('POSTGRES_DB', 'reddit_research'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', ''),
    }


def _build_conninfo() -> str:
    """Build connection string for psycopg pool."""
    config = get_db_config()
    return (
        f"host={config['host']} "
        f"port={config['port']} "
        f"dbname={config['dbname']} "
        f"user={config['user']} "
        f"password={config['password']}"
    )


# ============================================
# Connection Pool (Thread-Safe)
# ============================================

_pool: Optional[ConnectionPool] = None


def get_pool() -> ConnectionPool:
    """Get the global connection pool, creating it if needed."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            conninfo=_build_conninfo(),
            min_size=1,
            max_size=10,
            open=True,
        )
        atexit.register(_close_pool)
    return _pool


def _close_pool():
    """Close the connection pool on exit."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def close_pool():
    """Explicitly close the connection pool."""
    _close_pool()


# ============================================
# Context Managers
# ============================================

@contextmanager
def get_cursor(dict_cursor: bool = True):
    """
    Context manager for database cursor with auto-commit.
    Uses connection pool for thread safety.
    """
    pool = get_pool()
    row_factory = dict_row if dict_cursor else None

    with pool.connection() as conn:
        with conn.cursor(row_factory=row_factory) as cur:
            yield cur
            conn.commit()


@contextmanager
def get_connection():
    """Context manager for database connection from pool."""
    pool = get_pool()
    with pool.connection() as conn:
        yield conn


# ============================================
# Reddit Post Queries
# ============================================

def get_total_posts() -> int:
    """Get total count of posts in database."""
    with get_cursor(dict_cursor=False) as cur:
        cur.execute("SELECT COUNT(*) FROM reddit_posts")
        result = cur.fetchone()
        return result[0] if result else 0


def get_existing_post_ids() -> Set[str]:
    """Get all post IDs currently in database."""
    with get_cursor(dict_cursor=False) as cur:
        cur.execute("SELECT post_id FROM reddit_posts")
        return {row[0] for row in cur.fetchall()}


def get_post(post_id: str) -> Optional[Dict[str, Any]]:
    """Get a single post by ID."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM reddit_posts WHERE post_id = %s", (post_id,))
        return cur.fetchone()


def get_post_with_comments(post_id: str) -> Optional[Dict[str, Any]]:
    """Get a post with all its comments."""
    with get_cursor() as cur:
        cur.execute("SELECT * FROM reddit_posts WHERE post_id = %s", (post_id,))
        post = cur.fetchone()
        if not post:
            return None

        cur.execute(
            "SELECT * FROM reddit_comments WHERE post_id = %s ORDER BY created_utc",
            (post_id,)
        )
        comments = cur.fetchall()

        return {**post, 'comments': list(comments)}


def get_posts_by_subreddit(subreddit: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Get posts from a specific subreddit."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM reddit_posts WHERE subreddit = %s ORDER BY created_utc DESC LIMIT %s",
            (subreddit, limit)
        )
        return list(cur.fetchall())


def get_posts_for_classifier(classifier_type: str, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get posts that need classification for a specific classifier type.
    Only returns posts from subreddits mapped to this classifier.
    """
    status_table = f"{classifier_type}_post_status"

    with get_cursor() as cur:
        cur.execute(f"""
            SELECT p.*
            FROM reddit_posts p
            JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit
            LEFT JOIN {status_table} s ON p.post_id = s.post_id
            WHERE sc.classifier_type = %s
              AND (s.post_id IS NULL OR s.llm_processed = FALSE)
            ORDER BY p.created_utc DESC
            LIMIT %s
        """, (classifier_type, limit))
        return list(cur.fetchall())


# ============================================
# Comment Queries
# ============================================

def get_comments_for_post(post_id: str) -> List[Dict[str, Any]]:
    """Get all comments for a post, flattened."""
    with get_cursor() as cur:
        cur.execute(
            "SELECT * FROM reddit_comments WHERE post_id = %s ORDER BY created_utc",
            (post_id,)
        )
        return list(cur.fetchall())


# ============================================
# Bulk Insert Operations
# ============================================

def bulk_insert_posts(posts: List[Dict[str, Any]]) -> int:
    """
    Bulk insert posts with ON CONFLICT DO UPDATE.
    Returns number of posts processed.
    """
    if not posts:
        return 0

    with get_cursor() as cur:
        for post in posts:
            cur.execute("""
                INSERT INTO reddit_posts (
                    post_id, subreddit, title, selftext, author,
                    created_utc, score, num_comments, permalink, over_18
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (post_id) DO UPDATE SET
                    score = EXCLUDED.score,
                    num_comments = EXCLUDED.num_comments,
                    updated_at = NOW()
            """, (
                post.get('id'),
                post.get('subreddit'),
                post.get('title'),
                post.get('selftext'),
                post.get('author'),
                datetime.fromtimestamp(post.get('created_utc', 0), tz=timezone.utc),
                post.get('score'),
                post.get('num_comments'),
                post.get('permalink'),
                post.get('over_18', False),
            ))

    return len(posts)


def bulk_insert_comments(comments: List[Dict[str, Any]], post_id: str) -> int:
    """
    Bulk insert comments for a post with ON CONFLICT DO NOTHING.
    Comments can be nested - this flattens them.
    """
    if not comments:
        return 0

    def flatten_comments(comments_list: List[Dict], depth: int = 0) -> List[Dict]:
        """Recursively flatten nested comments."""
        flat = []
        for comment in comments_list:
            comment['_depth'] = depth
            flat.append(comment)
            # Handle nested replies
            replies = comment.get('replies')
            if isinstance(replies, dict):
                children = replies.get('data', {}).get('children', [])
                nested = [c['data'] for c in children if c.get('kind') == 't1']
                flat.extend(flatten_comments(nested, depth + 1))
        return flat

    flat_comments = flatten_comments(comments)

    with get_cursor() as cur:
        for comment in flat_comments:
            cur.execute("""
                INSERT INTO reddit_comments (
                    comment_id, post_id, parent_id, author, body,
                    score, created_utc, depth
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (comment_id) DO NOTHING
            """, (
                comment.get('id'),
                post_id,
                comment.get('parent_id'),
                comment.get('author'),
                comment.get('body'),
                comment.get('score'),
                datetime.fromtimestamp(comment.get('created_utc', 0), tz=timezone.utc),
                comment.get('_depth', 0),
            ))

    return len(flat_comments)


# ============================================
# Subreddit Classifier Mapping
# ============================================

def get_classifier_subreddits(classifier_type: str) -> List[str]:
    """Get subreddits mapped to a classifier type."""
    with get_cursor(dict_cursor=False) as cur:
        cur.execute(
            "SELECT subreddit FROM subreddit_classifiers WHERE classifier_type = %s",
            (classifier_type,)
        )
        return [row[0] for row in cur.fetchall()]


def set_subreddit_classifier(subreddit: str, classifier_type: str) -> None:
    """Map a subreddit to a classifier type."""
    with get_cursor() as cur:
        cur.execute("""
            INSERT INTO subreddit_classifiers (subreddit, classifier_type)
            VALUES (%s, %s)
            ON CONFLICT (subreddit) DO UPDATE SET classifier_type = EXCLUDED.classifier_type
        """, (subreddit, classifier_type))


# ============================================
# Classification Status
# ============================================

def update_post_status(classifier_type: str, post_id: str, data: Dict[str, Any]) -> None:
    """Update classification status for a post."""
    status_table = f"{classifier_type}_post_status"

    columns = list(data.keys())
    values = list(data.values())
    placeholders = ', '.join(['%s'] * len(columns))
    updates = ', '.join([f"{col} = EXCLUDED.{col}" for col in columns])

    with get_cursor() as cur:
        cur.execute(f"""
            INSERT INTO {status_table} (post_id, {', '.join(columns)})
            VALUES (%s, {placeholders})
            ON CONFLICT (post_id) DO UPDATE SET {updates}, updated_at = NOW()
        """, [post_id] + values)


def insert_classification_results(table_name: str, results: List[Dict[str, Any]]) -> int:
    """
    Insert multiple classification results (sources/solutions/experiences).
    Returns number of results inserted.
    """
    if not results:
        return 0

    with get_cursor() as cur:
        for result in results:
            columns = list(result.keys())
            values = list(result.values())
            placeholders = ', '.join(['%s'] * len(columns))

            cur.execute(f"""
                INSERT INTO {table_name} ({', '.join(columns)})
                VALUES ({placeholders})
            """, values)

    return len(results)


# ============================================
# Statistics
# ============================================

def get_post_stats() -> Dict[str, int]:
    """Get post statistics by subreddit."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT subreddit, COUNT(*) as count
            FROM reddit_posts
            GROUP BY subreddit
            ORDER BY count DESC
        """)
        return {row['subreddit']: row['count'] for row in cur.fetchall()}


def get_classification_stats(classifier_type: str) -> Dict[str, Any]:
    """Get classification progress for a classifier type."""
    status_table = f"{classifier_type}_post_status"

    with get_cursor() as cur:
        # Total posts for this classifier
        cur.execute("""
            SELECT COUNT(*) as count
            FROM reddit_posts p
            JOIN subreddit_classifiers sc ON p.subreddit = sc.subreddit
            WHERE sc.classifier_type = %s
        """, (classifier_type,))
        total = cur.fetchone()['count']

        # Processed posts
        cur.execute(f"""
            SELECT COUNT(*) as count FROM {status_table} WHERE llm_processed = TRUE
        """)
        processed = cur.fetchone()['count']

        return {
            'total': total,
            'processed': processed,
            'remaining': total - processed,
            'progress_pct': (processed / total * 100) if total > 0 else 0
        }


# ============================================
# Health Checks
# ============================================

def check_connection() -> bool:
    """Check if database connection works."""
    try:
        with get_cursor() as cur:
            cur.execute("SELECT 1")
            return True
    except Exception:
        return False


def check_tables_exist() -> Dict[str, bool]:
    """Check if required tables exist."""
    tables = [
        'reddit_posts', 'reddit_comments', 'subreddit_classifiers',
        'vintage_post_status', 'vintage_sources',
        'sex_post_status', 'sex_solutions',
        'housing_post_status', 'housing_experiences'
    ]
    results = {}

    with get_cursor() as cur:
        for table in tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                )
            """, (table,))
            results[table] = cur.fetchone()['exists']

    return results

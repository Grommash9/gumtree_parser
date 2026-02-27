"""
Base classifier for Reddit post/comment classification.
Abstract base class that defines the classification pipeline.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

from common.database import (
    get_post_with_comments,
    get_posts_for_classifier,
    update_post_status,
    insert_classification_results,
)
from common.config import PARALLEL_WORKERS
from llm_classifier.azure_client import call_llm, parse_json_response, parse_json_array_response


class BaseClassifier(ABC):
    """
    Abstract base class for Reddit post classifiers.

    Each classifier must implement:
    - classifier_type: Name of the classifier (vintage, sex, housing)
    - results_table: Name of the results table
    - get_stage0_prompt(): Relevance check prompt
    - get_stage1_prompt(): Extraction prompt
    - parse_stage0_response(): Parse relevance response
    - parse_stage1_response(): Parse extraction response
    """

    @property
    @abstractmethod
    def classifier_type(self) -> str:
        """Return classifier type name (vintage, sex, housing)."""
        pass

    @property
    @abstractmethod
    def results_table(self) -> str:
        """Return name of the results table."""
        pass

    @abstractmethod
    def get_stage0_prompt(self, document: str) -> str:
        """Generate Stage 0 prompt for relevance check."""
        pass

    @abstractmethod
    def get_stage1_prompt(self, document: str) -> str:
        """Generate Stage 1 prompt for extraction."""
        pass

    @abstractmethod
    def parse_stage0_response(self, response: str) -> Dict[str, Any]:
        """Parse Stage 0 response. Must return dict with 'is_relevant' key."""
        pass

    @abstractmethod
    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 response. Returns list of extracted items."""
        pass

    # Keywords that indicate potentially relevant comments (override in subclass)
    relevance_keywords: List[str] = []

    # Maximum comments to include
    max_comments: int = 50

    # Maximum document characters (~4000 tokens)
    max_doc_chars: int = 16000

    def build_document(self, post: Dict[str, Any]) -> str:
        """
        Build a single document from post + comments for LLM processing.
        Prioritizes relevant comments and limits document size.
        """
        lines = []

        # Post section
        lines.append("=== POST ===")
        lines.append(f"Title: {post.get('title', '')}")
        lines.append(f"Subreddit: r/{post.get('subreddit', '')}")
        lines.append("")

        selftext = post.get('selftext', '') or ''
        if selftext.strip():
            lines.append("Post Body:")
            lines.append(selftext)
            lines.append("")

        # Filter and prioritize comments
        comments = post.get('comments', [])
        selected_comments = self._select_comments(comments)

        if selected_comments:
            lines.append("=== COMMENTS ===")
            for i, comment in enumerate(selected_comments, 1):
                author = comment.get('author', '[deleted]')
                body = comment.get('body', '')
                score = comment.get('score', 0)

                lines.append(f"[Comment {i} (score: {score})]:")
                lines.append(body)
                lines.append("")

        doc = "\n".join(lines)

        # Truncate if too long
        if len(doc) > self.max_doc_chars:
            doc = doc[:self.max_doc_chars] + "\n... [truncated]"

        return doc

    def _select_comments(self, comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Select most relevant comments for processing.
        Prioritizes comments with keywords, then by score.
        """
        if not comments:
            return []

        # Filter out deleted/removed/empty comments
        valid_comments = [
            c for c in comments
            if c.get('body', '') not in ['[deleted]', '[removed]', '']
            and len(c.get('body', '')) > 10  # Skip very short comments
        ]

        if not valid_comments:
            return []

        # If we have relevance keywords, prioritize matching comments
        if self.relevance_keywords:
            keyword_matches = []
            other_comments = []

            for comment in valid_comments:
                body_lower = comment.get('body', '').lower()
                if any(kw in body_lower for kw in self.relevance_keywords):
                    keyword_matches.append(comment)
                else:
                    other_comments.append(comment)

            # Sort each group by score
            keyword_matches.sort(key=lambda x: x.get('score', 0), reverse=True)
            other_comments.sort(key=lambda x: x.get('score', 0), reverse=True)

            # Take keyword matches first, then fill with top-scored others
            selected = keyword_matches[:self.max_comments]
            remaining_slots = self.max_comments - len(selected)
            if remaining_slots > 0:
                selected.extend(other_comments[:remaining_slots])

            return selected
        else:
            # No keywords - just take top by score
            valid_comments.sort(key=lambda x: x.get('score', 0), reverse=True)
            return valid_comments[:self.max_comments]

    def classify_post(self, post_id: str) -> Dict[str, Any]:
        """
        Run full classification pipeline on a single post.
        Returns classification results.
        """
        # Get post with comments
        post = get_post_with_comments(post_id)
        if not post:
            return {'error': 'post_not_found', 'post_id': post_id}

        # Build document
        document = self.build_document(post)

        result = {
            'post_id': post_id,
            'subreddit': post.get('subreddit'),
            'stage_0_status': 'pending',
            'is_relevant': None,
            'llm_processed': False,
            'results': []
        }

        # Stage 0: Relevance check
        stage0_response = call_llm(
            prompt=self.get_stage0_prompt(document),
            system_message="You are a content classifier. Return only valid JSON.",
            post_id=post_id,
            stage="stage0"
        )

        if stage0_response is None:
            result['stage_0_status'] = 'failed'
            self._save_status(post_id, result)
            return result

        stage0_data = self.parse_stage0_response(stage0_response)
        result.update(stage0_data)
        result['stage_0_status'] = 'done'

        # If not relevant, skip Stage 1
        if not stage0_data.get('is_relevant', False):
            result['llm_processed'] = True
            self._save_status(post_id, result)
            return result

        # Stage 1: Extraction
        stage1_response = call_llm(
            prompt=self.get_stage1_prompt(document),
            system_message="You are a data extraction expert. Return only valid JSON.",
            post_id=post_id,
            stage="stage1",
            max_tokens=4000  # More tokens for potentially long extractions
        )

        if stage1_response is None:
            result['llm_processed'] = True  # Mark as processed even on failure
            self._save_status(post_id, result)
            return result

        # Parse and save results
        extracted_items = self.parse_stage1_response(stage1_response)
        result['results'] = extracted_items
        result['llm_processed'] = True

        # Save to database
        self._save_status(post_id, result)
        self._save_results(post_id, extracted_items)

        return result

    def _save_status(self, post_id: str, result: Dict[str, Any]) -> None:
        """Save classification status to database."""
        status_data = {
            'stage_0_status': result.get('stage_0_status', 'pending'),
            'is_relevant': result.get('is_relevant'),
            'llm_processed': result.get('llm_processed', False),
        }

        # Add classifier-specific fields
        extra_fields = self._get_extra_status_fields(result)
        status_data.update(extra_fields)

        update_post_status(self.classifier_type, post_id, status_data)

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Override to add classifier-specific status fields."""
        return {}

    def _save_results(self, post_id: str, items: List[Dict[str, Any]]) -> None:
        """Save extracted items to results table."""
        if not items:
            return

        # Add post_id to each item
        for item in items:
            item['post_id'] = post_id

        insert_classification_results(self.results_table, items)

    def _process_single(self, idx: int, total: int, post: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        """Process a single post. Returns (idx, classification_result)."""
        post_id = post['post_id']
        subreddit = post.get('subreddit', '?')

        try:
            classification = self.classify_post(post_id)

            if classification.get('is_relevant'):
                items_count = len(classification.get('results', []))
                print(f"[{idx}/{total}] r/{subreddit} - {post_id} ... RELEVANT ({items_count} items)", flush=True)
            else:
                print(f"[{idx}/{total}] r/{subreddit} - {post_id} ... not relevant", flush=True)

            return (idx, classification)

        except Exception as e:
            print(f"[{idx}/{total}] r/{subreddit} - {post_id} ... ERROR: {e}", flush=True)
            return (idx, {'error': str(e), 'post_id': post_id})

    def process_batch(self, limit: int = None) -> Dict[str, Any]:
        """
        Process a batch of posts for this classifier using parallel workers.
        Returns summary of processing results.
        """
        posts = get_posts_for_classifier(self.classifier_type, limit=limit)

        if not posts:
            return {
                'classifier': self.classifier_type,
                'processed': 0,
                'message': 'No posts to process'
            }

        total = len(posts)
        results = {
            'classifier': self.classifier_type,
            'total': total,
            'processed': 0,
            'relevant': 0,
            'items_extracted': 0,
            'errors': 0
        }

        print(f"\nProcessing {total} posts with {PARALLEL_WORKERS} workers...\n", flush=True)

        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as executor:
            futures = {
                executor.submit(self._process_single, idx, total, post): post
                for idx, post in enumerate(posts, 1)
            }

            for future in as_completed(futures):
                try:
                    idx, classification = future.result()
                    results['processed'] += 1

                    if classification.get('is_relevant'):
                        results['relevant'] += 1
                        results['items_extracted'] += len(classification.get('results', []))

                    if 'error' in classification:
                        results['errors'] += 1

                except Exception as e:
                    print(f"Future error: {e}", flush=True)
                    results['errors'] += 1

        return results

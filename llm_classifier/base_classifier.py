"""
Base classifier for Reddit post/comment classification.
Abstract base class that defines the classification pipeline.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from common.database import (
    get_post_with_comments,
    get_posts_for_classifier,
    update_post_status,
    insert_classification_results,
)
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

    def build_document(self, post: Dict[str, Any]) -> str:
        """
        Build a single document from post + comments for LLM processing.
        Returns concatenated text with clear sections.
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

        # Comments section
        comments = post.get('comments', [])
        if comments:
            lines.append("=== COMMENTS ===")
            for i, comment in enumerate(comments, 1):
                author = comment.get('author', '[deleted]')
                body = comment.get('body', '')
                score = comment.get('score', 0)
                depth = comment.get('depth', 0)

                # Skip deleted/removed comments
                if body in ['[deleted]', '[removed]', '']:
                    continue

                indent = "  " * depth
                lines.append(f"{indent}[Comment {i} by u/{author} (score: {score})]:")
                lines.append(f"{indent}{body}")
                lines.append("")

        return "\n".join(lines)

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

    def process_batch(self, limit: int = 50) -> Dict[str, Any]:
        """
        Process a batch of posts for this classifier.
        Returns summary of processing results.
        """
        posts = get_posts_for_classifier(self.classifier_type, limit=limit)

        if not posts:
            return {
                'classifier': self.classifier_type,
                'processed': 0,
                'message': 'No posts to process'
            }

        results = {
            'classifier': self.classifier_type,
            'total': len(posts),
            'processed': 0,
            'relevant': 0,
            'items_extracted': 0,
            'errors': 0
        }

        for post in posts:
            post_id = post['post_id']

            try:
                classification = self.classify_post(post_id)
                results['processed'] += 1

                if classification.get('is_relevant'):
                    results['relevant'] += 1
                    results['items_extracted'] += len(classification.get('results', []))

                if 'error' in classification:
                    results['errors'] += 1

            except Exception as e:
                print(f"Error processing {post_id}: {e}")
                results['errors'] += 1

        return results

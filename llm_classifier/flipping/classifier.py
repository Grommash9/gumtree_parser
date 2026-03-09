"""
Flipping/reselling feedback classifier.
Extracts user feedback about tools, software, and workflow pain points
from flipping/reselling subreddits, with author attribution.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response
from llm_classifier.flipping.prompts import get_stage0_prompt, get_stage1_prompt


class FlippingClassifier(BaseClassifier):
    """
    Classifier for extracting tool/workflow feedback from flipping subreddits.

    Key difference from other classifiers: preserves author usernames in the
    document sent to LLM for per-item attribution, and extracts structured
    feedback items (pains, likes, dislikes, feature requests).
    """

    relevance_keywords = [
        'software', 'tool', 'app', 'spreadsheet', 'inventory',
        'listing', 'crosslist', 'cross-list', 'crosspost',
        'scanner', 'barcode', 'pricer', 'repricing', 'repricer',
        'bookkeeping', 'accounting', 'tracking', 'profit',
        'workflow', 'automation', 'automate', 'bulk',
        'label', 'shipping', 'shipstation', 'pirateship',
        'selleramp', 'keepa', 'scoutiq', 'vendoo', 'list perfectly',
        'excel', 'google sheets', 'airtable',
        'hate', 'love', 'wish', 'annoying', 'frustrating', 'pain',
        'feature', 'missing', 'broken', 'bug', 'slow', 'clunky',
    ]

    @property
    def classifier_type(self) -> str:
        return "flipping"

    @property
    def results_table(self) -> str:
        return "flipping_feedback_items"

    def build_document(self, post: Dict[str, Any]) -> str:
        """
        Build document with author usernames included.
        Override base class to preserve author attribution needed for
        per-feedback-item author tracking.
        """
        lines = []

        # Post section with author
        lines.append("=== POST ===")
        lines.append(f"Title: {post.get('title', '')}")
        lines.append(f"Subreddit: r/{post.get('subreddit', '')}")
        post_author = post.get('author', '[deleted]')
        lines.append(f"Author: u/{post_author}")
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

                lines.append(f"[Comment {i} by u/{author} (score: {score})]:")
                lines.append(body)
                lines.append("")

        doc = "\n".join(lines)

        # Truncate if too long
        if len(doc) > self.max_doc_chars:
            doc = doc[:self.max_doc_chars] + "\n... [truncated]"

        return doc

    def get_stage0_prompt(self, document: str) -> str:
        return get_stage0_prompt(document)

    def get_stage1_prompt(self, document: str) -> str:
        return get_stage1_prompt(document)

    def parse_stage0_response(self, response: str) -> Dict[str, Any]:
        """Parse Stage 0 relevance check response."""
        result = parse_json_response(response)
        if not result:
            return {'is_relevant': False, 'mentions_tools': False}

        return {
            'is_relevant': result.get('is_relevant', False),
            'mentions_tools': result.get('mentions_tools', False),
        }

    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 extraction response into feedback items."""
        result = parse_json_response(response)
        if not result:
            return []

        items = result.get('feedback_items', [])
        if not isinstance(items, list):
            return []

        extracted = []
        for item in items:
            feedback = {
                'feedback_type': item.get('feedback_type'),
                'tool_or_area': item.get('tool_or_area'),
                'description': item.get('description'),
                'author': item.get('author'),
                'source': item.get('source', 'comment'),
                'original_quote': item.get('original_quote'),
                'sentiment_intensity': item.get('sentiment_intensity', 'medium'),
                'confidence': item.get('confidence'),
            }
            # Validate required fields
            if feedback['feedback_type'] and feedback['description']:
                # Validate enum values
                if feedback['feedback_type'] not in ('pain', 'like', 'dislike', 'feature_request'):
                    continue
                if feedback['source'] not in ('post', 'comment'):
                    feedback['source'] = 'comment'
                if feedback['sentiment_intensity'] not in ('low', 'medium', 'high'):
                    feedback['sentiment_intensity'] = 'medium'
                # Drop low-confidence items (borderline/irrelevant)
                if (feedback.get('confidence') or 0) < 0.75:
                    continue
                extracted.append(feedback)

        return extracted

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add flipping-specific status fields."""
        return {
            'mentions_tools': result.get('mentions_tools', False),
        }

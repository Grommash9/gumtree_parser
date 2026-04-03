"""
Flipping jokes/memes classifier.
Extracts funny one-liners and memes from flipping/reselling subreddits
and converts them into Minecraft-style splash texts for the app homescreen.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response
from llm_classifier.flipping_jokes.prompts import get_stage0_prompt, get_stage1_prompt


class FlippingJokesClassifier(BaseClassifier):
    """
    Classifier for extracting jokes and memes from flipping subreddits.

    Scans posts and comments for humor, funny observations, and relatable
    one-liners, then converts them into short splash texts suitable for
    a Minecraft-style app homescreen.
    """

    relevance_keywords = [
        'lol', 'lmao', 'haha', 'joke', 'meme', 'funny',
        'death pile', 'deathpile',
        'hoarding', 'hoarder', 'not hoarding',
        'garage', 'basement', 'storage unit',
        'spouse', 'wife', 'husband', 'partner',
        'lowball', 'lowballer', 'is this still available',
        'bought myself a job', 'side hustle',
        'dumpster', 'trash', 'junk',
        'profit', 'broke', 'rich',
        'addiction', 'addicted', 'obsess',
        'listing fatigue', 'hate listing', 'hate photos',
        'boot sale', 'car boot', 'garage sale',
        'thrift', 'goodwill', 'charity shop',
    ]

    @property
    def classifier_type(self) -> str:
        return "flipping_jokes"

    @property
    def results_table(self) -> str:
        return "flipping_jokes_items"

    def build_document(self, post: Dict[str, Any]) -> str:
        """
        Build document with author usernames preserved for attribution.
        """
        lines = []

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
            return {'is_relevant': False, 'has_humor': False}

        return {
            'is_relevant': result.get('is_relevant', False),
            'has_humor': result.get('has_humor', False),
        }

    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 extraction response into splash text items."""
        result = parse_json_response(response)
        if not result:
            return []

        items = result.get('splash_texts', [])
        if not isinstance(items, list):
            return []

        valid_categories = (
            'death_pile', 'money', 'sourcing', 'listing_fatigue',
            'buyers', 'lifestyle', 'shipping', 'family', 'finds',
            'self_deprecating',
        )

        extracted = []
        for item in items:
            splash = {
                'splash_text': item.get('splash_text'),
                'source_type': item.get('source_type', 'inspired'),
                'humor_category': item.get('humor_category'),
                'original_quote': item.get('original_quote'),
                'author': item.get('author'),
                'confidence': item.get('confidence'),
            }

            # Validate required fields
            if not splash['splash_text']:
                continue

            # Enforce max length
            if len(splash['splash_text']) > 80:
                splash['splash_text'] = splash['splash_text'][:77] + '...'

            # Validate enums
            if splash['source_type'] not in ('direct_quote', 'inspired'):
                splash['source_type'] = 'inspired'
            if splash['humor_category'] not in valid_categories:
                splash['humor_category'] = 'lifestyle'

            # Drop low-confidence items
            if (splash.get('confidence') or 0) < 0.7:
                continue

            extracted.append(splash)

        return extracted

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add jokes-specific status fields."""
        return {
            'has_humor': result.get('has_humor', False),
        }

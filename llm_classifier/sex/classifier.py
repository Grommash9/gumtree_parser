"""
Sex/Intimacy solutions classifier.
Extracts information about what helped people restore intimacy in relationships.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response, call_llm
from llm_classifier.sex.prompts import (
    get_stage0_prompt,
    get_stage0_post_only_prompt,
    get_stage05_batch_prompt,
    get_stage1_prompt,
)
from common.database import get_post_with_comments, update_post_status, insert_classification_results


class SexClassifier(BaseClassifier):
    """
    Classifier for extracting relationship/intimacy solutions.

    Uses 3-stage batch processing to reduce context:
    - Stage 0: Post-only relevance check
    - Stage 0.5: Batch screening of comments
    - Stage 1: Extraction from relevant batches only

    Extracts:
    - Solutions that helped restore intimacy
    - Categories of advice (communication, therapy, medical, etc.)
    - Whether solutions worked
    - Relationship context
    """

    # Batch size for comment processing
    batch_size: int = 10

    @property
    def classifier_type(self) -> str:
        return "sex"

    @property
    def results_table(self) -> str:
        return "sex_solutions"

    def get_stage0_prompt(self, document: str) -> str:
        return get_stage0_prompt(document)

    def get_stage1_prompt(self, document: str) -> str:
        return get_stage1_prompt(document)

    def parse_stage0_response(self, response: str) -> Dict[str, Any]:
        """Parse Stage 0 relevance check response."""
        result = parse_json_response(response)
        if not result:
            return {
                'is_relevant': False,
                'mentions_solutions': False,
            }

        return {
            'is_relevant': result.get('is_relevant', False),
            'mentions_solutions': result.get('mentions_solutions', False),
        }

    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 extraction response."""
        result = parse_json_response(response)
        if not result:
            return []

        solutions = result.get('solutions', [])
        if not isinstance(solutions, list):
            return []

        # Transform to match database schema
        extracted = []
        for solution in solutions:
            item = {
                'solution_category': solution.get('solution_category'),
                'solution_description': solution.get('solution_description'),
                'worked': solution.get('worked'),
                'timeframe': solution.get('timeframe'),
                'relationship_context': solution.get('relationship_context'),
                'original_quote': solution.get('original_quote'),
                'confidence': solution.get('confidence'),
            }
            # Only include items with at least a description
            if item['solution_description']:
                extracted.append(item)

        return extracted

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add sex-specific status fields."""
        return {
            'mentions_solutions': result.get('mentions_solutions', False)
        }

    def _build_comment_batches(self, comments: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split comments into batches for processing."""
        # Filter valid comments first
        valid_comments = [
            c for c in comments
            if c.get('body', '') not in ['[deleted]', '[removed]', '']
            and len(c.get('body', '')) > 10
        ]

        # Sort by score (best first)
        valid_comments.sort(key=lambda x: x.get('score', 0), reverse=True)

        # Split into batches
        batches = []
        for i in range(0, len(valid_comments), self.batch_size):
            batch = valid_comments[i:i + self.batch_size]
            if batch:
                batches.append(batch)

        return batches

    def _format_batch_for_screening(self, batch: List[Dict[str, Any]]) -> str:
        """Format a batch of comments for the screening prompt."""
        lines = []
        for i, comment in enumerate(batch, 1):
            body = comment.get('body', '')
            score = comment.get('score', 0)
            lines.append(f"[Comment {i} (score: {score})]:")
            lines.append(body)
            lines.append("")
        return "\n".join(lines)

    def _build_batch_document(self, post: Dict[str, Any], comments: List[Dict[str, Any]]) -> str:
        """Build document from post + specific comments for extraction."""
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
        if comments:
            lines.append("=== COMMENTS ===")
            for i, comment in enumerate(comments, 1):
                body = comment.get('body', '')
                score = comment.get('score', 0)
                lines.append(f"[Comment {i} (score: {score})]:")
                lines.append(body)
                lines.append("")

        return "\n".join(lines)

    def classify_post(self, post_id: str) -> Dict[str, Any]:
        """
        Run 3-stage batch classification pipeline:
        - Stage 0: Post-only relevance check
        - Stage 0.5: Batch screening of comments
        - Stage 1: Extraction from relevant batches only
        """
        # Get post with comments
        post = get_post_with_comments(post_id)
        if not post:
            return {'error': 'post_not_found', 'post_id': post_id}

        result = {
            'post_id': post_id,
            'subreddit': post.get('subreddit'),
            'stage_0_status': 'pending',
            'is_relevant': None,
            'mentions_solutions': False,
            'llm_processed': False,
            'results': [],
            'batches_screened': 0,
            'batches_relevant': 0,
        }

        # === Stage 0: Post-only relevance check ===
        stage0_prompt = get_stage0_post_only_prompt(
            title=post.get('title', ''),
            subreddit=post.get('subreddit', ''),
            body=post.get('selftext', '') or ''
        )

        stage0_response = call_llm(
            prompt=stage0_prompt,
            system_message="You are a content classifier. Return only valid JSON.",
            post_id=post_id,
            stage="stage0"
        )

        if stage0_response is None:
            result['stage_0_status'] = 'failed'
            self._save_status(post_id, result)
            return result

        stage0_data = parse_json_response(stage0_response)
        if not stage0_data or not stage0_data.get('is_relevant', False):
            result['stage_0_status'] = 'done'
            result['is_relevant'] = False
            result['llm_processed'] = True
            self._save_status(post_id, result)
            return result

        result['stage_0_status'] = 'done'

        # === Stage 0.5: Batch screening ===
        comments = post.get('comments', [])
        batches = self._build_comment_batches(comments)
        result['batches_screened'] = len(batches)

        relevant_comments = []

        for batch_idx, batch in enumerate(batches):
            batch_text = self._format_batch_for_screening(batch)
            screen_prompt = get_stage05_batch_prompt(batch_text)

            screen_response = call_llm(
                prompt=screen_prompt,
                system_message="You are a content classifier. Return only valid JSON.",
                post_id=post_id,
                stage=f"stage05_batch{batch_idx}"
            )

            if screen_response:
                screen_data = parse_json_response(screen_response)
                if screen_data and screen_data.get('has_solutions', False):
                    relevant_comments.extend(batch)
                    result['batches_relevant'] += 1

        # If no relevant batches found, mark as not relevant
        if not relevant_comments:
            result['is_relevant'] = False
            result['llm_processed'] = True
            self._save_status(post_id, result)
            return result

        result['is_relevant'] = True
        result['mentions_solutions'] = True

        # === Stage 1: Extraction from relevant comments only ===
        extraction_doc = self._build_batch_document(post, relevant_comments)

        stage1_response = call_llm(
            prompt=get_stage1_prompt(extraction_doc),
            system_message="You are a data extraction expert. Return only valid JSON.",
            post_id=post_id,
            stage="stage1",
            max_tokens=4000
        )

        if stage1_response is None:
            result['llm_processed'] = True
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
            'mentions_solutions': result.get('mentions_solutions', False),
        }
        update_post_status(self.classifier_type, post_id, status_data)

    def _save_results(self, post_id: str, items: List[Dict[str, Any]]) -> None:
        """Save extracted items to results table."""
        if not items:
            return

        for item in items:
            item['post_id'] = post_id

        insert_classification_results(self.results_table, items)

"""
Sex/Intimacy solutions classifier.
Extracts information about what helped people restore intimacy in relationships.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response
from llm_classifier.sex.prompts import get_stage0_prompt, get_stage1_prompt


class SexClassifier(BaseClassifier):
    """
    Classifier for extracting relationship/intimacy solutions.

    Extracts:
    - Solutions that helped restore intimacy
    - Categories of advice (communication, therapy, medical, etc.)
    - Whether solutions worked
    - Relationship context
    """

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

"""
Housing/Shared Ownership experiences classifier.
Extracts information about shared ownership experiences in the UK.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response
from llm_classifier.housing.prompts import get_stage0_prompt, get_stage1_prompt


class HousingClassifier(BaseClassifier):
    """
    Classifier for extracting shared ownership housing experiences.

    Extracts:
    - Positive and negative experiences
    - Warnings and tips
    - Categories (staircasing, service charges, selling, etc.)
    - Housing association names
    - Location information
    """

    @property
    def classifier_type(self) -> str:
        return "housing"

    @property
    def results_table(self) -> str:
        return "housing_experiences"

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
                'is_shared_ownership': False,
            }

        return {
            'is_relevant': result.get('is_relevant', False),
            'is_shared_ownership': result.get('is_shared_ownership', False),
        }

    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 extraction response."""
        result = parse_json_response(response)
        if not result:
            return []

        experiences = result.get('experiences', [])
        if not isinstance(experiences, list):
            return []

        # Transform to match database schema
        extracted = []
        for exp in experiences:
            item = {
                'experience_type': exp.get('experience_type'),
                'experience_summary': exp.get('experience_summary'),
                'category': exp.get('category'),
                'housing_association': exp.get('housing_association'),
                'location': exp.get('location'),
                'original_quote': exp.get('original_quote'),
                'confidence': exp.get('confidence'),
            }
            # Only include items with at least a summary
            if item['experience_summary']:
                extracted.append(item)

        return extracted

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add housing-specific status fields."""
        return {
            'is_shared_ownership': result.get('is_shared_ownership', False)
        }

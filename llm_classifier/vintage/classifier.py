"""
Vintage sourcing market classifier.
Extracts information about where people find vintage items.
"""

from typing import Dict, Any, List

from llm_classifier.base_classifier import BaseClassifier
from llm_classifier.azure_client import parse_json_response
from llm_classifier.vintage.prompts import get_stage0_prompt, get_stage1_prompt


class VintageClassifier(BaseClassifier):
    """
    Classifier for extracting vintage item sourcing markets.

    Extracts:
    - Flea markets, estate sales, thrift stores, etc.
    - Names, locations, frequencies
    - Types of items found, price quality
    """

    @property
    def classifier_type(self) -> str:
        return "vintage"

    @property
    def results_table(self) -> str:
        return "vintage_sources"

    def get_stage0_prompt(self, document: str) -> str:
        return get_stage0_prompt(document)

    def get_stage1_prompt(self, document: str) -> str:
        return get_stage1_prompt(document)

    def parse_stage0_response(self, response: str) -> Dict[str, Any]:
        """Parse Stage 0 relevance check response."""
        result = parse_json_response(response)
        if not result:
            return {'is_relevant': False, 'relevance_reason': 'Failed to parse response'}

        # Must be UK AND have named source to be relevant
        is_uk = result.get('is_uk', False)
        has_named_source = result.get('has_named_source', False)
        is_relevant = result.get('is_relevant', False) and is_uk and has_named_source

        return {
            'is_relevant': is_relevant,
            'relevance_reason': result.get('reason', '')
        }

    def parse_stage1_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse Stage 1 extraction response."""
        result = parse_json_response(response)
        if not result:
            return []

        sources = result.get('sources', [])
        if not isinstance(sources, list):
            return []

        # Transform to match database schema
        extracted = []
        for source in sources:
            item = {
                'source_type': source.get('source_type'),
                'source_name': source.get('source_name'),
                'source_location': source.get('source_location'),
                'source_frequency': source.get('source_frequency'),
                'item_categories': source.get('item_categories'),  # PostgreSQL array
                'price_quality': source.get('price_quality'),
                'original_quote': source.get('original_quote'),
                'confidence': source.get('confidence'),
            }
            # Only include items with at least a source_type
            if item['source_type']:
                extracted.append(item)

        return extracted

    def _get_extra_status_fields(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Add vintage-specific status fields."""
        return {
            'relevance_reason': result.get('relevance_reason', '')
        }

"""
Prompts for Vintage sourcing market classifier.
Extracts information about where people find vintage items.
"""


STAGE0_SYSTEM = "You are a content classifier. Return only valid JSON."

STAGE0_PROMPT = """Analyze this Reddit post and comments to determine if it mentions any SOURCING LOCATIONS for vintage, antique, or collectible items.

We are looking for mentions of:
- Flea markets
- Estate sales
- Garage/yard sales
- Thrift stores (Goodwill, Salvation Army, charity shops, etc.)
- Antique malls/shops
- Auctions (live or online)
- Boot sales / car boot sales
- Swap meets
- Online marketplaces (eBay, Etsy, Facebook Marketplace, etc.)
- Any other places where people find vintage items

{document}

Return a JSON object:
{{
    "is_relevant": true/false,
    "reason": "Brief explanation of why this is or isn't relevant"
}}

Only return is_relevant=true if the post or comments mention SPECIFIC places or types of places where items are sourced/found.
General discussion about vintage items without mentioning where they were found is NOT relevant."""


STAGE1_PROMPT = """Extract ALL sourcing locations mentioned in this Reddit post and comments.

{document}

For EACH sourcing location mentioned, extract:
- source_type: One of: flea_market, estate_sale, garage_sale, thrift_store, antique_shop, auction, boot_sale, swap_meet, online, other
- source_name: Specific name if mentioned (e.g., "Rose Bowl Flea Market", "Goodwill", "Long Beach Antique Market")
- source_location: City, state, country if mentioned
- source_frequency: How often it runs (weekly, monthly, annual, one-time) if mentioned
- item_categories: What types of items are found there (array)
- price_quality: cheap, good_deals, expensive, mixed, or null
- original_quote: The exact text that mentions this source (keep it brief, 1-2 sentences max)
- confidence: Your confidence score 0.0-1.0

Return a JSON object:
{{
    "sources": [
        {{
            "source_type": "flea_market",
            "source_name": "Rose Bowl Flea Market",
            "source_location": "Pasadena, California",
            "source_frequency": "monthly",
            "item_categories": ["furniture", "vintage clothing", "collectibles"],
            "price_quality": "mixed",
            "original_quote": "I found this at the Rose Bowl flea market last month",
            "confidence": 0.95
        }}
    ]
}}

Important:
- Extract EVERY source mentioned, even if only briefly
- Include sources from both the post AND comments
- If the same source is mentioned multiple times, only include it once
- If no sources are found, return {{"sources": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

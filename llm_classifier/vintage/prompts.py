"""
Prompts for Vintage sourcing market classifier.
Extracts information about where people find vintage items in the UK.
"""


STAGE0_SYSTEM = "You are a content classifier. Return only valid JSON."

STAGE0_PROMPT = """Analyze this Reddit post and comments to determine if it mentions SPECIFIC NAMED sourcing locations for vintage, antique, or collectible items IN THE UK.

We are ONLY interested in:
- UK-based locations (England, Scotland, Wales, Northern Ireland)
- SPECIFIC NAMED places (e.g., "Sunbury Antiques Market", "Newark Antiques Fair", "Ardingly", "Kempton Park")
- Car boot sales with specific names/locations
- Charity shops with location (e.g., "British Heart Foundation in Manchester")
- Antique centres/malls with names
- Auction houses with names (e.g., "Hansons", "Fieldings")

We are NOT interested in:
- Generic mentions without specific names (e.g., just "charity shops" or "car boot sales")
- US/non-UK locations
- Online-only sources (eBay, Etsy, Facebook Marketplace)
- Vague references without a specific place name

{document}

Return a JSON object:
{{
    "is_relevant": true/false,
    "is_uk": true/false,
    "has_named_source": true/false,
    "reason": "Brief explanation"
}}

Return is_relevant=true ONLY if:
1. The content is clearly about UK locations (is_uk=true)
2. At least one SPECIFIC NAMED source is mentioned (has_named_source=true)

If unsure whether it's UK or if no specific names are mentioned, return is_relevant=false."""


STAGE1_PROMPT = """Extract ALL NAMED UK sourcing locations mentioned in this Reddit post and comments.

{document}

For EACH sourcing location mentioned, extract:
- source_type: One of: antique_fair, antique_centre, car_boot_sale, charity_shop, auction_house, flea_market, vintage_shop, other
- source_name: The SPECIFIC NAME (REQUIRED - skip if no name given)
- source_location: City, county, or region in UK
- source_frequency: How often it runs (weekly, monthly, annual, one-time) if mentioned
- item_categories: What types of items are found there (array)
- price_quality: cheap, good_deals, expensive, mixed, or null
- original_quote: The exact text that mentions this source (keep it brief, 1-2 sentences max)
- confidence: Your confidence score 0.0-1.0

Return a JSON object:
{{
    "sources": [
        {{
            "source_type": "antique_fair",
            "source_name": "Newark Antiques Fair",
            "source_location": "Newark, Nottinghamshire",
            "source_frequency": "monthly",
            "item_categories": ["furniture", "ceramics", "silver"],
            "price_quality": "mixed",
            "original_quote": "Newark is brilliant for furniture, I go every month",
            "confidence": 0.95
        }},
        {{
            "source_type": "car_boot_sale",
            "source_name": "Denham Car Boot",
            "source_location": "Denham, Buckinghamshire",
            "source_frequency": "weekly",
            "item_categories": ["bric-a-brac", "vintage"],
            "price_quality": "cheap",
            "original_quote": "Denham car boot on Sundays is great",
            "confidence": 0.9
        }}
    ]
}}

IMPORTANT RULES:
- ONLY include UK locations
- ONLY include sources with SPECIFIC NAMES (skip generic "charity shops" or "local car boot")
- Skip online marketplaces (eBay, Etsy, Facebook, Vinted, etc.)
- Include sources from both the post AND comments
- If the same source is mentioned multiple times, only include it once
- If no NAMED UK sources are found, return {{"sources": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

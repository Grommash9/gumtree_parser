"""
Prompts for Housing/Shared Ownership experiences classifier.
Extracts information about shared ownership experiences in the UK.
"""


STAGE0_PROMPT = """Analyze this Reddit post and comments to determine if it discusses SHARED OWNERSHIP housing experiences in the UK.

Shared ownership is a UK government scheme where you buy a share of a property (usually 25-75%) and pay rent on the remaining share.

We are looking for:
- Personal experiences with shared ownership
- Advice about buying/selling shared ownership properties
- Experiences with housing associations
- Information about staircasing (buying additional shares)
- Service charges and fees experiences
- Positive or negative experiences with shared ownership

{document}

Return a JSON object:
{{
    "is_relevant": true/false,
    "is_shared_ownership": true/false,
    "reason": "Brief explanation"
}}

Return is_relevant=true ONLY if:
- The post/comments discuss shared ownership specifically
- There are personal experiences or advice about shared ownership
- Content is about UK housing shared ownership scheme

Do NOT mark as relevant if:
- It's about general house buying/renting without shared ownership
- It's about shared housing/flatmates (different from shared ownership)
- It's not UK-specific"""


STAGE1_PROMPT = """Extract ALL shared ownership experiences and advice mentioned in this Reddit post and comments.

{document}

For EACH experience or piece of advice mentioned, extract:
- experience_type: One of: positive, negative, warning, tip, question, neutral
- experience_summary: What was the experience or advice
- category: One of: buying, selling, staircasing, service_charges, rent, housing_association, legal, mortgage, valuation, resale, other
- housing_association: Name of housing association if mentioned
- location: Area/region if mentioned
- original_quote: The exact text describing this experience (keep brief, 1-2 sentences)
- confidence: Your confidence score 0.0-1.0

Return a JSON object:
{{
    "experiences": [
        {{
            "experience_type": "warning",
            "experience_summary": "Service charges increased significantly after purchase, from 1200 to 2400 per year",
            "category": "service_charges",
            "housing_association": "L&Q",
            "location": "London",
            "original_quote": "Watch out for service charges, ours doubled in 2 years...",
            "confidence": 0.9
        }}
    ]
}}

Important:
- Extract EVERY experience or piece of advice, even small ones
- Include experiences from both the post AND comments
- Differentiate between positive, negative, and neutral experiences
- Capture warnings and tips separately
- If no shared ownership experiences are found, return {{"experiences": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

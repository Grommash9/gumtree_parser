"""
Prompts for Vintage sourcing market classifier.
Extracts UK locations where people find vintage/antique items to resell.
"""


STAGE0_SYSTEM = "You are a content classifier. Return only valid JSON."

STAGE0_PROMPT = """Analyze this UK Reddit post. Does it mention WHERE to SOURCE vintage, antique, or secondhand items for reselling?

This is from a UK subreddit, so all mentions are UK-based unless explicitly stated otherwise.

VALID - we want posts discussing:
- Car boot sales (any mention - "car boots", "boot sales", specific names like Denham, Wimbledon)
- Charity shops (any mention for sourcing/reselling purposes)
- Antique fairs/markets (Newark, Ardingly, Sunbury, or generic "antique fairs")
- Auction houses (Hansons, Fieldings, or "local auctions")
- Antique centres/shops
- House clearances, estate sales
- Flea markets, jumble sales
- Tips about physical places to find items to flip/resell

NOT VALID - ignore:
- Food/drink venues (chip shops, cafes, restaurants)
- New furniture retailers (DFS, Sofology, IKEA)
- Record shops, music stores
- Bullion/coin dealers
- Museums, gift shops
- Online-only platforms (eBay, Etsy, Facebook, Vinted, Depop)
- US stores (Goodwill, Value Village, Savers, thrift stores)
- Posts ONLY about selling items, not sourcing them

{document}

Return JSON:
{{
    "is_relevant": true/false,
    "reason": "Brief explanation"
}}

Return is_relevant=true if post mentions any physical places/venues for sourcing secondhand items."""


STAGE1_PROMPT = """Extract sourcing locations from this UK Reddit post and comments.

This is from a UK subreddit - assume all mentions are UK-based.

{document}

EXTRACT these venue types:
1. CAR BOOT SALES: Any car boot mention (specific name or generic "car boots")
2. CHARITY SHOPS: Any charity shop mention for sourcing/reselling
3. ANTIQUE FAIRS: Newark, Ardingly, Sunbury, or generic "antique fairs"
4. AUCTION HOUSES: Named houses or generic "auctions"/"local auctions"
5. ANTIQUE CENTRES/SHOPS: Named or generic mentions
6. HOUSE CLEARANCES/ESTATE SALES
7. FLEA MARKETS, JUMBLE SALES

DO NOT extract:
- Food venues (chip shops, cafes, restaurants)
- New furniture retailers (DFS, IKEA)
- Record/music shops
- Online platforms (eBay, Vinted, Facebook)
- US stores (Goodwill, thrift stores)

Return JSON:
{{
    "sources": [
        {{
            "source_type": "car_boot_sale",
            "source_name": "Car boot sales",
            "source_location": "UK (general)",
            "source_frequency": "weekly",
            "item_categories": ["general"],
            "price_quality": "cheap",
            "original_quote": "I source from car boots",
            "confidence": 0.8
        }}
    ]
}}

Notes:
- source_type: car_boot_sale, charity_shop, antique_fair, auction_house, antique_centre, flea_market, house_clearance, jumble_sale
- source_name: Specific name if mentioned, or generic like "Car boot sales", "Charity shops"
- source_location: Named location if mentioned, otherwise "UK (general)"
- Extract ALL distinct sourcing venues/types mentioned
- If no sourcing venues mentioned, return {{"sources": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

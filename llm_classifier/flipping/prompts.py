"""
Prompts for Flipping/reselling feedback classifier.
Extracts user feedback about tools, software, and workflow pain points.
"""


STAGE0_PROMPT = """You are helping a product team that builds software for flipping/resellers. We need to find posts where people reveal UNMET NEEDS, WORKFLOW BOTTLENECKS, or GAPS IN EXISTING TOOLS — insights that tell us what to build or improve.

Analyze this Reddit post. Does it contain ACTIONABLE PRODUCT INSIGHTS for a team building reselling software?

RELEVANT — posts that reveal:
- WORKFLOW PAIN POINTS: "I spend 2 hours a day manually entering items into spreadsheets" → opportunity to automate
- TOOL FRUSTRATIONS: "Vendoo keeps crashing when I crosslist to Mercari" → specific UX/reliability gap to exploit
- UNMET NEEDS: "I wish there was an app that scans a barcode and tells me the profit margin" → feature to build
- TOOL COMPARISONS: "I switched from List Perfectly to Vendoo because..." → competitive intelligence
- WORKFLOW DESCRIPTIONS with friction: "My process is: photo → spreadsheet → list on 3 platforms → track in another sheet" → integration opportunity
- TIME/MONEY WASTE: "I pay for 3 different subscriptions just to manage inventory" → consolidation opportunity
- FEATURE GAPS: "SellerAmp doesn't show Mercari comps" → specific missing feature

NOT RELEVANT — posts with no product insight:
- Marketplace policy complaints (fees, suspensions, algorithm) with no tool angle
- Buyer/seller behavior (scammers, lowballers, flaky buyers)
- Shipping carrier service quality (USPS delays, FedEx damage)
- Business strategy (what to sell, when to lower prices, ROI)
- Sourcing advice, haul posts, "what's this worth?"
- Generic tool mentions without opinion ("I use eBay" — so what?)
- Simple tool recommendations with no WHY ("just use Vendoo" — no insight)
- Platform built-in features used as intended with no friction ("I click sell-similar" — that's just using eBay)

{document}

Return JSON:
{{
    "is_relevant": true/false,
    "mentions_tools": true/false,
    "reason": "Brief explanation of the product insight, or why there is none"
}}

Ask yourself: "Would a product manager read this and learn something actionable?" If not, return is_relevant=false."""


STAGE1_PROMPT = """You are helping a product team that builds software for flipping/resellers. Extract ACTIONABLE PRODUCT INSIGHTS from this post — things that tell us what to build, what to fix, or what gap to fill.

{document}

For each insight, identify:

1. **feedback_type**:
   - "pain" = workflow bottleneck or frustration that software could solve (e.g., "I spend hours manually entering data across 3 platforms")
   - "like" = specific tool/feature that works well and we should learn from (e.g., "Vendoo's one-click crosslist to 5 platforms saves me hours")
   - "dislike" = specific tool/feature that fails users — a gap we can exploit (e.g., "List Perfectly crashes constantly on large inventories")
   - "feature_request" = explicit wish or unmet need (e.g., "I wish one app handled inventory, listing, AND profit tracking together")

2. **tool_or_area**: The specific tool or workflow area (e.g., "Vendoo", "crosslisting", "inventory tracking", "profit calculation"). Use the tool name if one is mentioned, otherwise describe the workflow area.

3. **description**: The actionable insight — what would a product manager learn from this? Frame it as an opportunity, not just a restatement.

4. **author**: Reddit username of the person who said this.

5. **source**: "post" or "comment"

6. **original_quote**: The exact text (max ~200 chars)

7. **sentiment_intensity**:
   - "low" = passing mention
   - "medium" = clear opinion with specifics
   - "high" = strong emotion, detailed experience, or affects many users

8. **confidence**: 0.0-1.0 — how confident this is a genuine, actionable product insight

Return JSON:
{{
    "feedback_items": [
        {{
            "feedback_type": "pain",
            "tool_or_area": "inventory management",
            "description": "Users manually track inventory in spreadsheets across multiple platforms — opportunity for unified inventory sync",
            "author": "FlipKing99",
            "source": "comment",
            "original_quote": "I have 3 spreadsheets just to track what's listed where and what sold...",
            "sentiment_intensity": "high",
            "confidence": 0.95
        }}
    ]
}}

EXTRACT only if it answers one of these questions:
- What workflow takes too much time/effort? (→ automation opportunity)
- What existing tool is broken/slow/missing features? (→ competitive gap)
- What do users wish existed? (→ feature to build)
- What tool do users love and why? (→ pattern to replicate)
- What do users pay for that disappoints them? (→ market entry point)

DO NOT EXTRACT:
- Generic tool mentions with no opinion or insight ("I use eBay")
- Marketplace policy complaints (fees, suspensions) — no product action
- Carrier service complaints (USPS lost package) — can't build around this
- Business strategy (pricing, sourcing, what to sell) — not a tool insight
- Using a platform's basic features as intended with no friction ("I click sell-similar")
- "Thank you" or agreement comments with no new information

If no actionable product insights are found, return {{"feedback_items": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

"""
Prompts for Flipping jokes/memes classifier.
Finds funny one-liners and memes from flipping/reselling communities
and converts them into Minecraft-style splash texts.

V2 — Improved based on analysis of 80k results from V1:
- Removed example splash texts from Stage 1 (LLM parroted them back thousands of times)
- Strongly prefer direct_quote over inspired (V1 produced mostly generic LLM-generated lines)
- Added explicit anti-generic rules and banned phrases
- Tightened Stage 0 to reduce false positives (V1: 24% hit rate, mostly not actually funny)
- Added uniqueness requirement — the value is in SPECIFIC, ORIGINAL humor from the community
"""


STAGE0_PROMPT = """You are scanning Reddit posts from flipping/reselling communities for GENUINELY FUNNY content — real jokes, witty observations, and laugh-out-loud moments that only resellers would truly get.

Analyze this Reddit post. Does it contain something actually funny?

RELEVANT — posts where someone actually said something funny:
- A SPECIFIC funny observation or story (not a generic complaint)
- WITTY WORDING — the humor is in HOW they said it, not just what they said
- COMMUNITY IN-JOKES that make resellers laugh (death pile, the lowball ritual, etc.)
- ABSURD SITUATIONS described in an entertaining way
- SELF-AWARE HUMOR about the ridiculousness of the reseller life

NOT RELEVANT — even if the topic is about flipping:
- Serious posts that happen to mention funny topics (death piles, lowballers) but aren't actually funny
- Generic complaints without wit ("shipping is expensive" — that's just a fact, not a joke)
- Posts where the topic is humorous but the writing is dry/boring
- Standard questions, advice, strategy, hauls, finds without funny commentary
- Posts that are only mildly amusing — we want GENUINELY FUNNY, not "slightly relatable"

{document}

Return JSON:
{{
    "is_relevant": true/false,
    "has_humor": true/false,
    "reason": "Quote the funniest line from the post, or explain why nothing is genuinely funny"
}}

QUALITY BAR: Be strict. If you wouldn't actually chuckle reading it, it's not relevant. We want the top 5-10% funniest posts, not everything that mentions a humorous topic."""


STAGE1_PROMPT = """You are mining Reddit posts for ORIGINAL, SPECIFIC funny lines from the flipping/reselling community. These will become short "splash texts" (like Minecraft title screen text) on an app homescreen.

Your job: find the FUNNIEST ACTUAL QUOTES from this post and clean them up into punchy one-liners.

{document}

=== CRITICAL RULES ===

1. EXTRACT, DON'T INVENT. Your splash_text must be based on something ACTUALLY SAID in the post.
   - GOOD: User wrote "my spare room looks like a charity shop exploded" → "My spare room looks like a charity shop exploded"
   - BAD: Post mentions death piles → you generate "It's not hoarding if you're gonna list it" (generic, not from the post)

2. PRESERVE THE ORIGINAL VOICE. The humor is in the specific way the Redditor said it. Don't sand it down into a generic motivational poster.
   - GOOD: "I told my wife it was research, not shopping"
   - BAD: "Spouses just don't understand the hustle!" (generic, lost the original wit)

3. BANNED — Do NOT output any of these overused lines or close variants:
   - "It's not hoarding if you're gonna list/sell/flip it"
   - "Your garage called. It wants its space back"
   - "Congrats, you bought yourself a job"
   - "Revenue is not profit"
   - "Another day, another boot sale"
   - "Still better than a spreadsheet"
   - "One man's trash is another man's treasure"
   - "The thrill of the hunt"
   - "Turning trash into cash/treasure"
   - "Buy low, sell high"
   - Any generic "X: the real Y of reselling!" pattern
   - Any generic "X is just a badge of honor!" pattern
   - Any "[noun] gonna [same noun]!" pattern (e.g., "lowballers gonna lowball")
   If your output matches or closely resembles any of these, DISCARD IT and look for something original.

4. MAX 3 ITEMS per post. Only the genuinely funny ones. Zero is fine if nothing is good enough.

5. SHORT — 60 chars ideal, 80 max. One sentence. No hashtags, no emojis.

6. STANDALONE — Must be funny without context. If you need to explain it, skip it.

7. FAMILY-FRIENDLY — No profanity or offensive content.

8. NO PLATFORM NAMES — Replace "eBay/Poshmark/Mercari/Vinted" with generic terms if needed.

For each splash text, provide:

1. **splash_text**: The final polished one-liner (max 80 chars). Must be ORIGINAL to this post.
2. **source_type**: "direct_quote" (cleaned/shortened from actual text) or "inspired" (rephrased, but the CORE IDEA must be from the post — not your invention)
3. **humor_category**: one of:
   - "death_pile" — inventory piles, hoarding, storage chaos
   - "money" — profit delusions, fees eating margins, "investments"
   - "sourcing" — thrift stores, garage sales, estate sales, dumpster diving
   - "listing_fatigue" — photography, descriptions, crosslisting tedium
   - "buyers" — lowballers, ghosting, "is this still available?", scammers
   - "lifestyle" — the reseller grind, work-life balance, obsession
   - "shipping" — packaging, labels, post office, carriers
   - "family" — spouse/partner/family reactions to the hobby
   - "finds" — amazing scores, terrible buys, the hunt
   - "self_deprecating" — roasting yourself as a reseller
4. **original_quote**: The EXACT text from the post/comment this came from (max 200 chars). This MUST be a real quote from the document above — not paraphrased, not invented.
5. **author**: Reddit username of who said it
6. **confidence**: 0.0-1.0 — how funny AND original is this? Only 0.85+ for lines that would make a reseller genuinely laugh.

Return JSON:
{{
    "splash_texts": [
        {{
            "splash_text": "My spare room looks like a charity shop exploded",
            "source_type": "direct_quote",
            "humor_category": "death_pile",
            "original_quote": "honestly my spare room looks like a charity shop exploded in there, the wife is NOT happy",
            "author": "bootlegflip",
            "confidence": 0.92
        }}
    ]
}}

FINAL CHECK before returning: For each item, ask yourself:
- Is this ACTUALLY from the post, or did I make it up? (If made up → DELETE)
- Have I seen this exact phrase 1000 times before? (If yes → DELETE)
- Would a reseller genuinely laugh, or just nod? (If just nod → DELETE)
- Is the original_quote a real quote from the document? (If not → DELETE)

If nothing passes these checks, return {{"splash_texts": []}} — that's perfectly fine."""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

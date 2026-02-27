"""
Prompts for Sex/Intimacy solutions classifier.
Extracts information about what helped people restore intimacy in relationships.

Uses a 3-stage approach to reduce context:
- Stage 0: Post-only relevance check
- Stage 0.5: Batch screening of comments
- Stage 1: Extraction from relevant batches only
"""


# Stage 0: Post-only relevance check (minimal context)
STAGE0_POST_ONLY_PROMPT = """Analyze this Reddit post title and body. Is it discussing intimacy/relationship issues where SOLUTIONS might be shared?

=== POST ===
Title: {title}
Subreddit: r/{subreddit}

{body}

Return JSON:
{{
    "is_relevant": true/false,
    "reason": "Brief explanation"
}}

Return is_relevant=true if:
- Post is about intimacy/relationship/bedroom issues
- Comments might contain solutions or advice
- Topic is appropriate for sharing what helped

Return false if:
- Off-topic (not about relationships/intimacy)
- Just venting with no possibility of solution discussion
- Purely asking questions with no comments expected to have solutions"""


# Stage 0.5: Batch screening for comments that mention solutions
STAGE05_BATCH_PROMPT = """Do any of these comments mention SOLUTIONS or THINGS THAT HELPED with intimacy/relationship issues?

{comments}

Return JSON:
{{
    "has_solutions": true/false
}}

Return has_solutions=true if ANY comment mentions:
- Something that worked or helped
- Advice that was successful
- Actions that improved the situation
- Therapy, communication, medical solutions, etc.

Return false if comments only contain:
- Questions without answers
- Complaints without solutions
- General discussion without actionable advice"""


# Original Stage 0 prompt (kept for backwards compatibility)
STAGE0_PROMPT = """Analyze this Reddit post and comments to determine if it discusses SOLUTIONS or THINGS THAT HELPED restore intimacy or improve sexual/romantic aspects of a relationship.

We are looking for:
- Solutions that worked to improve intimacy
- Advice that helped restore sexual connection
- Actions that improved bedroom/romantic situations
- Success stories about overcoming intimacy issues

{document}

Return a JSON object:
{{
    "is_relevant": true/false,
    "mentions_solutions": true/false,
    "reason": "Brief explanation"
}}

Return is_relevant=true ONLY if:
- The post/comments mention specific solutions, actions, or advice that HELPED
- There are success stories or positive outcomes described
- Someone shares what worked for them

Do NOT mark as relevant if it's only:
- Complaining about problems without solutions
- Asking for advice without any solutions in comments
- Discussing issues without mentioning what helped"""


STAGE1_PROMPT = """Extract ALL solutions and advice mentioned in this Reddit post and comments that helped restore intimacy or improve relationships.

{document}

For EACH solution mentioned, extract:
- solution_category: One of: communication, therapy, medical, lifestyle, scheduling, date_nights, physical_intimacy, emotional_connection, boundary_setting, professional_help, self_improvement, other
- solution_description: What exactly was the solution/advice
- worked: true if it helped, false if it didn't, null if unclear
- timeframe: How long until results were seen (if mentioned)
- relationship_context: Context about the relationship (married, dating, years together)
- original_quote: The exact text describing this solution (keep brief, 1-2 sentences)
- confidence: Your confidence score 0.0-1.0

Return a JSON object:
{{
    "solutions": [
        {{
            "solution_category": "communication",
            "solution_description": "Started having weekly check-in conversations about needs and desires",
            "worked": true,
            "timeframe": "2-3 months",
            "relationship_context": "Married 10 years",
            "original_quote": "What really helped us was scheduling a weekly talk...",
            "confidence": 0.9
        }}
    ]
}}

Important:
- Extract EVERY solution mentioned, even partial ones
- Include solutions from both the post AND comments
- Focus on WHAT HELPED, not just problems discussed
- If multiple people share the same type of solution, include each as separate entry
- If no solutions are found, return {{"solutions": []}}"""


def get_stage0_prompt(document: str) -> str:
    """Generate Stage 0 relevance check prompt (legacy - full document)."""
    return STAGE0_PROMPT.format(document=document)


def get_stage0_post_only_prompt(title: str, subreddit: str, body: str) -> str:
    """Generate Stage 0 post-only relevance check prompt."""
    body_text = body.strip() if body else "(no body)"
    return STAGE0_POST_ONLY_PROMPT.format(title=title, subreddit=subreddit, body=body_text)


def get_stage05_batch_prompt(comments: str) -> str:
    """Generate Stage 0.5 batch screening prompt."""
    return STAGE05_BATCH_PROMPT.format(comments=comments)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

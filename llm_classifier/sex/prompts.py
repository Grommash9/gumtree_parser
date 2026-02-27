"""
Prompts for Sex/Intimacy solutions classifier.
Extracts information about what helped people restore intimacy in relationships.
"""


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
    """Generate Stage 0 relevance check prompt."""
    return STAGE0_PROMPT.format(document=document)


def get_stage1_prompt(document: str) -> str:
    """Generate Stage 1 extraction prompt."""
    return STAGE1_PROMPT.format(document=document)

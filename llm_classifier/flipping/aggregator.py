"""
Topic aggregator for flipping feedback items.
Uses two-pass LLM clustering to group similar feedback across posts
into actionable topics with stats and priority scoring.
"""

from typing import Dict, Any, List

from common.database import (
    get_feedback_items_for_aggregation,
    create_aggregation_run,
    update_aggregation_run,
    insert_topic,
    insert_topic_item_mappings,
    update_topic_stats,
)
from llm_classifier.azure_client import call_llm, parse_json_response


# Priority weights by feedback type
TYPE_WEIGHTS = {
    'pain': 3,
    'feature_request': 3,
    'dislike': 2,
    'like': 1,
}

SENTIMENT_SCORES = {
    'low': 1,
    'medium': 2,
    'high': 3,
}

BATCH_SIZE = 50


def _build_batch_cluster_prompt(items: List[Dict[str, Any]], feedback_type: str) -> str:
    """Build prompt for Pass 1: cluster a batch of items into topics."""
    items_text = []
    for item in items:
        items_text.append(
            f"[ID:{item['id']}] \"{item['description']}\" "
            f"(tool: {item.get('tool_or_area', 'N/A')}, "
            f"by u/{item.get('author', '?')})"
        )

    items_block = "\n".join(items_text)

    return f"""You are analyzing {len(items)} feedback items of type "{feedback_type}" from flipping/reselling Reddit users.

Group these items into logical TOPICS. Each topic should represent a distinct, actionable insight.

Items:
{items_block}

Rules:
- Create 3-15 topics depending on how diverse the items are
- Each item must belong to exactly one topic
- Topic titles should be specific and actionable (e.g., "Manual data entry across multiple platforms" not "General complaints")
- Include tools_mentioned: list of specific tool/app names mentioned in the items

Return JSON:
{{
    "topics": [
        {{
            "topic_title": "Descriptive actionable title",
            "topic_summary": "2-3 sentence summary of what users are saying",
            "tools_mentioned": ["eBay", "Vendoo"],
            "item_ids": [1, 2, 5]
        }}
    ]
}}

Every item ID must appear in exactly one topic."""


def _build_merge_prompt(topics: List[Dict[str, Any]]) -> str:
    """Build prompt for Pass 2: merge duplicate/overlapping topics across batches."""
    topics_text = []
    for i, topic in enumerate(topics):
        topics_text.append(
            f"[Topic {i}] \"{topic['topic_title']}\" "
            f"({topic['total_item_count']} items, {topic['unique_user_count']} users) - "
            f"{topic['topic_summary']}"
        )

    topics_block = "\n".join(topics_text)

    return f"""You are merging topic clusters from a feedback analysis. Some topics from different batches may be duplicates or overlap significantly.

Topics to merge:
{topics_block}

Rules:
- Merge topics that describe the same underlying issue/theme
- Keep topics separate if they address genuinely different concerns, even if related
- Produce a final clean list of distinct topics
- For merged topics, combine the titles into a better one and merge summaries

Return JSON:
{{
    "merged_topics": [
        {{
            "final_title": "Best descriptive title for merged topic",
            "final_summary": "Combined 2-3 sentence summary",
            "source_topic_indices": [0, 3],
            "tools_mentioned": ["eBay", "Vendoo"]
        }}
    ]
}}

Each original topic index must appear in exactly one merged group (even if it's a group of 1)."""


class TopicAggregator:
    """
    Two-pass LLM clustering for feedback topic aggregation.

    Pass 1: Cluster batches of ~50 items into intermediate topics
    Pass 2: Merge intermediate topics across batches to deduplicate
    """

    def run(self, limit_per_type: int = None) -> Dict[str, Any]:
        """Run full aggregation pipeline. Returns summary stats.

        Args:
            limit_per_type: Max items per feedback type (for testing). None = all.
        """
        run_id = create_aggregation_run()
        total_items = 0
        total_topics = 0

        try:
            for feedback_type in ['pain', 'feature_request', 'dislike', 'like']:
                items = get_feedback_items_for_aggregation(feedback_type)
                if limit_per_type and len(items) > limit_per_type:
                    items = items[:limit_per_type]
                if not items:
                    print(f"  No items for type '{feedback_type}', skipping.")
                    continue

                total_items += len(items)
                print(f"\n  Processing {len(items)} '{feedback_type}' items...")

                # Pass 1: Batch clustering
                intermediate_topics = self._pass1_batch_cluster(items, feedback_type)
                print(f"    Pass 1: {len(intermediate_topics)} intermediate topics")

                if not intermediate_topics:
                    continue

                # Pass 2: Cross-batch merge (only if multiple batches produced topics)
                if len(intermediate_topics) > 15:
                    final_topics = self._pass2_merge(intermediate_topics, feedback_type)
                    print(f"    Pass 2: merged into {len(final_topics)} final topics")
                else:
                    final_topics = intermediate_topics

                # Save to database
                for topic_data in final_topics:
                    topic_data['feedback_type'] = feedback_type
                    self._compute_priority(topic_data, feedback_type)
                    topic_id = insert_topic(run_id, topic_data)
                    insert_topic_item_mappings(topic_id, topic_data.get('_item_ids', []))
                    update_topic_stats(topic_id)
                    total_topics += 1

            update_aggregation_run(run_id, total_items, total_topics, 'completed')
            return {
                'run_id': run_id,
                'items_processed': total_items,
                'topics_created': total_topics,
                'status': 'completed',
            }

        except Exception as e:
            update_aggregation_run(run_id, total_items, total_topics, 'failed')
            raise

    def _pass1_batch_cluster(
        self, items: List[Dict[str, Any]], feedback_type: str
    ) -> List[Dict[str, Any]]:
        """Pass 1: cluster items in batches of BATCH_SIZE."""
        all_topics = []
        total_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE

        for batch_idx, batch_start in enumerate(range(0, len(items), BATCH_SIZE), 1):
            batch = items[batch_start:batch_start + BATCH_SIZE]
            print(f"    Batch {batch_idx}/{total_batches} ({len(batch)} items)...", flush=True)
            prompt = _build_batch_cluster_prompt(batch, feedback_type)

            response = call_llm(
                prompt=prompt,
                system_message="You are a data analyst. Return only valid JSON.",
                post_id=f"agg_{feedback_type}_{batch_start}",
                stage="aggregation_pass1",
                max_tokens=4000,
            )

            if response is None:
                print(f"    Warning: LLM returned None for batch starting at {batch_start}")
                continue

            parsed = parse_json_response(response)
            if not parsed or 'topics' not in parsed:
                continue

            # Build item ID lookup for this batch
            batch_id_map = {item['id']: item for item in batch}

            for topic in parsed['topics']:
                item_ids = topic.get('item_ids', [])
                # Resolve to actual DB IDs (LLM returns the IDs we gave it)
                valid_ids = [iid for iid in item_ids if iid in batch_id_map]

                # Compute user count from actual items
                authors = set()
                for iid in valid_ids:
                    author = batch_id_map[iid].get('author')
                    if author and author != '[deleted]':
                        authors.add(author)

                all_topics.append({
                    'topic_title': topic.get('topic_title', 'Unknown'),
                    'topic_summary': topic.get('topic_summary', ''),
                    'tools_mentioned': topic.get('tools_mentioned', []),
                    'unique_user_count': len(authors),
                    'total_item_count': len(valid_ids),
                    '_item_ids': valid_ids,
                })

        return all_topics

    def _pass2_merge(
        self, topics: List[Dict[str, Any]], feedback_type: str
    ) -> List[Dict[str, Any]]:
        """Pass 2: merge overlapping topics from different batches."""
        prompt = _build_merge_prompt(topics)

        response = call_llm(
            prompt=prompt,
            system_message="You are a data analyst. Return only valid JSON.",
            post_id=f"agg_{feedback_type}_merge",
            stage="aggregation_pass2",
            max_tokens=4000,
        )

        if response is None:
            return topics  # Fall back to unmerged

        parsed = parse_json_response(response)
        if not parsed or 'merged_topics' not in parsed:
            return topics

        merged = []
        for mt in parsed['merged_topics']:
            source_indices = mt.get('source_topic_indices', [])
            # Combine item IDs from all source topics
            combined_ids = []
            combined_tools = set()
            for idx in source_indices:
                if 0 <= idx < len(topics):
                    combined_ids.extend(topics[idx].get('_item_ids', []))
                    for tool in topics[idx].get('tools_mentioned', []):
                        combined_tools.add(tool)

            # Deduplicate item IDs
            combined_ids = list(set(combined_ids))

            merged.append({
                'topic_title': mt.get('final_title', 'Unknown'),
                'topic_summary': mt.get('final_summary', ''),
                'tools_mentioned': list(combined_tools | set(mt.get('tools_mentioned', []))),
                'unique_user_count': 0,  # Will be recomputed from DB
                'total_item_count': len(combined_ids),
                '_item_ids': combined_ids,
            })

        return merged

    def _compute_priority(self, topic_data: Dict[str, Any], feedback_type: str) -> None:
        """Compute priority score: unique_users * type_weight * avg_sentiment."""
        type_weight = TYPE_WEIGHTS.get(feedback_type, 1)
        user_count = topic_data.get('unique_user_count', 0)
        # Default to medium sentiment (2) as actual per-item sentiment
        # would require loading all items again
        avg_sentiment = 2
        topic_data['priority_score'] = user_count * type_weight * avg_sentiment

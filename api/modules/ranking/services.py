"""
Ranking Services
================
Helper functions for popularity decay math and collaborative filtering.

These are pure functions (no side effects) — they compute scores from
raw data. The Celery tasks in `tasks.py` call these and write the results.
"""

import math
import logging
from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)

# ── Popularity Scoring ──────────────────────────────────────────────────────

# Half-life for recency decay: content older than this many hours loses
# ~50% of its raw engagement weight.
POPULARITY_HALF_LIFE_HOURS = 72  # 3 days

# Weights for different event types in the popularity formula.
# Higher weight = stronger signal of content quality.
EVENT_WEIGHTS = {
    'watch': 1.0,
    'replay': 2.0,
    'like': 3.0,
    'save': 5.0,
    'share': 6.0,
    'comment': 4.0,
    'follow': 3.0,
    'skip': -1.0,
    'not_interested': -5.0,
    'hide': -3.0,
    'report': -10.0,
    # Rewatch / revisit event types (Blueprint §5-§8)
    'revisit': 1.5,              # User scrolled back — moderate positive
    'rewatch': 5.0,              # Intentional rewatch — strong positive
    'rewatch_complete': 7.0,     # Completed a rewatch — very strong positive
    'navigation_back': 0.0,     # Neutral navigation signal
}


def compute_popularity_score(event_rows, now=None):
    """
    Compute a recency-decayed popularity score per content_id.

    Args:
        event_rows: iterable of dicts with keys:
            content_id, event_type, watch_pct, timestamp
        now: current time (defaults to timezone.now())

    Returns:
        dict of {content_id: float_score}
    """
    if now is None:
        now = timezone.now()

    scores = defaultdict(float)

    for row in event_rows:
        content_id = row['content_id']
        event_type = row['event_type']
        watch_pct = row.get('watch_pct', 0.0)
        timestamp = row['timestamp']

        # Base weight from event type
        base_weight = EVENT_WEIGHTS.get(event_type, 0.0)

        # Bonus for watch completion (only for watch/replay events)
        if event_type in ('watch', 'replay'):
            # Scale the weight by how much was actually watched
            # Full completion (1.0) gets full weight; 10% gets 10%
            base_weight *= max(watch_pct, 0.1)  # Floor at 10% to avoid zeros

        # Exponential time decay
        age_hours = (now - timestamp).total_seconds() / 3600.0
        decay = math.exp(-0.693 * age_hours / POPULARITY_HALF_LIFE_HOURS)

        scores[content_id] += base_weight * decay

    return dict(scores)


# ── Collaborative Filtering ────────────────────────────────────────────────

def compute_cf_scores(event_rows, min_cowatch=2):
    """
    Simple item-item collaborative filtering based on co-watch patterns.

    "Users who engaged with X also engaged with Y" — computes a similarity
    score for each content pair, then for each content_id returns the
    average similarity across its neighbors.

    Args:
        event_rows: iterable of dicts with keys: user_id, content_id, event_type
        min_cowatch: minimum number of co-watching users to consider a pair

    Returns:
        dict of {content_id: float_cf_score}

    This is intentionally simple (pandas-free for small scale). For larger
    event logs, the Celery task uses pandas for the same computation.
    """
    # Step 1: Build user → set of content_ids they engaged with positively
    POSITIVE_EVENTS = {'watch', 'replay', 'like', 'save', 'share', 'comment', 'follow'}
    user_items = defaultdict(set)

    for row in event_rows:
        if row['event_type'] in POSITIVE_EVENTS:
            user_items[row['user_id']].add(row['content_id'])

    # Step 2: Build co-occurrence matrix
    # For each pair of items, count how many users engaged with both
    cowatch_counts = defaultdict(lambda: defaultdict(int))
    item_counts = defaultdict(int)

    for user_id, items in user_items.items():
        items_list = list(items)
        for item in items_list:
            item_counts[item] += 1
        for i, item_a in enumerate(items_list):
            for item_b in items_list[i + 1:]:
                cowatch_counts[item_a][item_b] += 1
                cowatch_counts[item_b][item_a] += 1

    # Step 3: Compute similarity (Jaccard-like) and average CF score
    cf_scores = {}
    for item_a in item_counts:
        similarities = []
        for item_b, cowatch in cowatch_counts[item_a].items():
            if cowatch < min_cowatch:
                continue
            # Jaccard similarity: |A ∩ B| / |A ∪ B|
            union = item_counts[item_a] + item_counts[item_b] - cowatch
            if union > 0:
                similarities.append(cowatch / union)

        if similarities:
            cf_scores[item_a] = sum(similarities) / len(similarities)
        else:
            cf_scores[item_a] = 0.0

    return cf_scores

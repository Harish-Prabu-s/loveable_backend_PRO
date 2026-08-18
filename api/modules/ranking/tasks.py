"""
Ranking Tasks — Celery Periodic Jobs
=====================================
Task 2: compute_popularity_and_cf (hourly) — reads events, computes scores
Task 3: rebuild_user_feeds (every 5 min) — builds per-user feed into Redis

These are registered in CELERY_BEAT_SCHEDULE in settings.py.
"""

import json
import logging
from datetime import timedelta

import redis
from celery import shared_task
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from .services import compute_popularity_score, compute_cf_scores

logger = logging.getLogger(__name__)


def _get_cache_redis():
    """Get Redis connection for the feed cache (DB 3)."""
    return redis.Redis.from_url(
        settings.REDIS_CACHE_URL,
        decode_responses=True,
    )


# ── Task 2: Popularity + Collaborative Filtering ───────────────────────────

@shared_task(name='api.modules.ranking.tasks.compute_popularity_and_cf')
def compute_popularity_and_cf():
    """
    Hourly Celery Beat task.

    1. Queries the RecEvent table for the last 7 days of events.
    2. Computes recency-decayed popularity score per content_id.
    3. Computes item-item CF scores from co-watch patterns.
    4. Writes/upserts results into the ContentScore table.
    """
    from api.modules.rec_events.models import RecEvent
    from .models import ContentScore

    lookback = timezone.now() - timedelta(days=7)

    # Fetch recent events — only the fields we need
    events = list(
        RecEvent.objects.filter(
            timestamp__gte=lookback,
            is_flagged=False,  # Exclude abuse-flagged events
        ).values(
            'user_id', 'content_id', 'event_type', 'watch_pct', 'timestamp',
        )
    )

    if not events:
        logger.info('compute_popularity_and_cf: no events in the last 7 days.')
        return {'content_ids_updated': 0}

    logger.info(f'compute_popularity_and_cf: processing {len(events)} events.')

    # Compute popularity scores
    pop_scores = compute_popularity_score(events)

    # Compute CF scores
    cf_scores = compute_cf_scores(events)

    # Get all unique content_ids
    all_content_ids = set(pop_scores.keys()) | set(cf_scores.keys())

    # Upsert into ContentScore
    updated = 0
    for content_id in all_content_ids:
        pop = pop_scores.get(content_id, 0.0)
        cf = cf_scores.get(content_id, 0.0)
        combined = (0.6 * pop) + (0.4 * cf)

        obj, created = ContentScore.objects.update_or_create(
            content_id=content_id,
            defaults={
                'popularity_score': pop,
                'cf_score': cf,
                'combined_score': combined,
            },
        )
        updated += 1

    logger.info(f'compute_popularity_and_cf: updated {updated} content scores.')
    return {'content_ids_updated': updated}


# ── Task 3: Feed Builder ───────────────────────────────────────────────────

FEED_SIZE = 20  # Number of items per user feed
FEED_TTL_SECONDS = 600  # Feed cache expires in 10 minutes (refreshed every 5)


@shared_task(name='api.modules.ranking.tasks.rebuild_user_feeds')
def rebuild_user_feeds():
    """
    Every-5-minutes Celery Beat task.

    For each active user (users who had events in the last 24h):
    1. Reads top N ContentScore entries.
    2. Joins content metadata (cdn_url, thumbnail, caption, creator).
    3. Writes the assembled feed JSON to Redis key `feed:{user_id}`.

    The DRF Feed API reads ONLY from this Redis key — zero MySQL queries
    on the hot path.
    """
    from api.modules.rec_events.models import RecEvent
    from api.models import Reel
    from .models import ContentScore

    # Find active users (had events in the last 24 hours)
    cutoff = timezone.now() - timedelta(hours=24)
    active_user_ids = list(
        RecEvent.objects.filter(timestamp__gte=cutoff)
        .values_list('user_id', flat=True)
        .distinct()
    )

    if not active_user_ids:
        logger.info('rebuild_user_feeds: no active users.')
        return {'feeds_built': 0}

    # Get top content by combined_score
    top_content = list(
        ContentScore.objects.order_by('-combined_score')
        .values_list('content_id', flat=True)[:200]  # Pool of candidates
    )

    if not top_content:
        logger.info('rebuild_user_feeds: no content scores available.')
        return {'feeds_built': 0}

    # Pre-fetch content metadata for the candidate pool
    reels = Reel.objects.filter(
        id__in=top_content, is_archived=False,
    ).select_related('user__profile').values(
        'id', 'user_id', 'caption', 'created_at',
        'engagement_score', 'view_count', 'share_count',
    )

    # Build a lookup dict for content metadata
    content_meta = {}
    for reel in reels:
        content_meta[reel['id']] = {
            'content_id': reel['id'],
            'type': 'reel',
            'creator_id': reel['user_id'],
            'caption': (reel['caption'] or '')[:200],  # Truncate for cache
            'created_at': reel['created_at'].isoformat() if reel['created_at'] else None,
            'engagement_score': reel['engagement_score'],
            'view_count': reel['view_count'],
            'share_count': reel['share_count'],
        }

    # Get per-user event history for basic personalization filtering
    r = _get_cache_redis()
    feeds_built = 0

    for user_id in active_user_ids:
        try:
            # Get content this user has already seen / interacted with
            seen_content_ids = set(
                RecEvent.objects.filter(
                    user_id=user_id,
                    timestamp__gte=cutoff,
                    event_type__in=['watch', 'like', 'not_interested', 'hide'],
                ).values_list('content_id', flat=True)
            )

            # Filter out seen content and build the feed
            feed_items = []
            for content_id in top_content:
                if content_id in seen_content_ids:
                    continue
                meta = content_meta.get(content_id)
                if meta:
                    feed_items.append(meta)
                if len(feed_items) >= FEED_SIZE:
                    break

            # If not enough unseen content, pad with top content (allow re-shows)
            if len(feed_items) < FEED_SIZE:
                for content_id in top_content:
                    meta = content_meta.get(content_id)
                    if meta and meta not in feed_items:
                        feed_items.append(meta)
                    if len(feed_items) >= FEED_SIZE:
                        break

            # Write to Redis
            feed_key = f'feed:{user_id}'
            r.set(feed_key, json.dumps(feed_items), ex=FEED_TTL_SECONDS)
            feeds_built += 1

        except Exception as e:
            logger.error(f'Failed to build feed for user {user_id}: {e}')
            continue

    logger.info(f'rebuild_user_feeds: built {feeds_built} feeds for {len(active_user_ids)} active users.')
    return {'feeds_built': feeds_built}

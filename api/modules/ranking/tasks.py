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
from .deep_ranker import ranker
from .diversity import apply_mmr

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
            'user_id', 'content_id', 'content_type', 'event_type', 'watch_pct', 'timestamp',
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
    for key in all_content_ids:
        content_type, content_id = key
        pop = pop_scores.get(key, 0.0)
        cf = cf_scores.get(key, 0.0)
        combined = (0.6 * pop) + (0.4 * cf)

        obj, created = ContentScore.objects.update_or_create(
            content_type=content_type,
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
NUM_PAGES = 3   # Pre-compute this many pages
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
    top_scores = list(
        ContentScore.objects.order_by('-combined_score')
        .values('content_id', 'content_type')[:200]  # Pool of candidates
    )
    top_content_keys = [(s['content_type'], s['content_id']) for s in top_scores]

    if not top_content_keys:
        logger.info('rebuild_user_feeds: no content scores available.')
        return {'feeds_built': 0}

    # Pre-fetch creator quality scores for all active creators
    from .models import CreatorScore
    from api.modules.embeddings.retrieval import vector_index
    import numpy as np

    creator_scores_qs = CreatorScore.objects.all().values_list('creator_id', 'quality_score')
    creator_scores = {cid: score for cid, score in creator_scores_qs}

    # Pre-fetch content metadata for the candidate pool
    from api.models import Post
    reel_ids = [k[1] for k in top_content_keys if k[0] == 'reel']
    post_ids = [k[1] for k in top_content_keys if k[0] == 'post']

    reels = Reel.objects.filter(
        id__in=reel_ids, is_archived=False,
    ).select_related('user__profile').values(
        'id', 'user_id', 'caption', 'created_at',
        'engagement_score', 'view_count', 'share_count',
    )
    posts = Post.objects.filter(
        id__in=post_ids, is_archived=False,
    ).select_related('user__profile').values(
        'id', 'user_id', 'caption', 'created_at',
        'engagement_score', 'view_count', 'share_count',
    )

    # Build a lookup dict for content metadata
    content_meta = {}
    for reel in reels:
        # Get tags for topic matching
        tags = [] # Tags prefetching omitted for simplicity in this snippet, will fetch if needed
        content_meta[('reel', reel['id'])] = {
            'content_id': reel['id'],
            'type': 'reel',
            'creator_id': reel['user_id'],
            'caption': (reel['caption'] or '')[:200],  # Truncate for cache
            'created_at': reel['created_at'].isoformat() if reel['created_at'] else None,
            'engagement_score': reel['engagement_score'],
            'view_count': reel['view_count'],
            'share_count': reel['share_count'],
            'tags': tags,
        }
    for post in posts:
        tags = []
        content_meta[('post', post['id'])] = {
            'content_id': post['id'],
            'type': 'post',
            'creator_id': post['user_id'],
            'caption': (post['caption'] or '')[:200],
            'created_at': post['created_at'].isoformat() if post['created_at'] else None,
            'engagement_score': post['engagement_score'],
            'view_count': post['view_count'],
            'share_count': post['share_count'],
            'tags': tags,
        }

    # Get per-user event history for basic personalization filtering
    r = _get_cache_redis()
    feeds_built = 0

    for user_id in active_user_ids:
        try:
            # 1. Get seen content from ultra-fast Redis Set
            from api.modules.rec_filter.seen import get_seen_items
            seen_content_ids = get_seen_items(user_id)

            # 2. Fetch User Interest Profile from Redis
            profile_json = r.get(f'profile:{user_id}')
            profile = json.loads(profile_json) if profile_json else {}
            
            long_term = profile.get('long_term', {})
            short_term = profile.get('short_term', {})
            session = profile.get('session', {})
            negative = profile.get('negative_confidence', {})

            # 2.5 FAISS Retrieval (Phase 3.2)
            # Find the user's top interest topic to query the vector index
            user_candidates = set(top_content_keys)
            
            if long_term and vector_index.index is not None:
                # Get the user's top interest topic
                top_topic = max(long_term.items(), key=lambda x: x[1])[0]
                
                # We need the vector representation of this topic.
                # In a real system, we'd query a dictionary of topic embeddings.
                # For this MVP, we'll fetch a recent popular post with this tag and use its embedding as a proxy.
                try:
                    from api.modules.embeddings.models import ContentEmbedding
                    from api.models import Reel
                    
                    # Find a reel with this hashtag
                    proxy_reel = Reel.objects.filter(hashtags__name=top_topic).order_by('-view_count').first()
                    if proxy_reel:
                        emb_record = ContentEmbedding.objects.filter(content_id=proxy_reel.id, content_type='reel').first()
                        if emb_record:
                            query_vec = emb_record.get_embedding()
                            if query_vec is not None:
                                faiss_results = vector_index.search(query_vec, k=50)
                                faiss_ids = [res[0] for res in faiss_results]
                                
                                # Add these FAISS candidates to our pool (assume reels for MVP)
                                user_candidates.update(('reel', fid) for fid in faiss_ids)
                except Exception as e:
                    logger.warning(f"FAISS retrieval failed for user {user_id}: {e}")

            # 3. Score candidates
            scored_candidates = []
            for content_key in user_candidates:
                content_type, content_id = content_key
                if content_id in seen_content_ids:
                    continue
                
                meta = content_meta.get(content_key)
                if not meta:
                    try:
                        if content_type == 'reel':
                            reel = Reel.objects.get(id=content_id)
                            tags = [] # Tags prefetching omitted
                            meta = {
                                'content_id': reel.id,
                                'type': 'reel',
                                'creator_id': reel.user_id,
                                'caption': (reel.caption or '')[:200],
                                'created_at': reel.created_at.isoformat() if reel.created_at else None,
                                'engagement_score': reel.engagement_score,
                                'view_count': reel.view_count,
                                'share_count': reel.share_count,
                                'tags': tags,
                            }
                        else:
                            post = Post.objects.get(id=content_id)
                            tags = []
                            meta = {
                                'content_id': post.id,
                                'type': 'post',
                                'creator_id': post.user_id,
                                'caption': (post.caption or '')[:200],
                                'created_at': post.created_at.isoformat() if post.created_at else None,
                                'engagement_score': post.engagement_score,
                                'view_count': post.view_count,
                                'share_count': post.share_count,
                                'tags': tags,
                            }
                        content_meta[content_key] = meta
                    except (Reel.DoesNotExist, Post.DoesNotExist):
                        continue
                    
                # Calculate Personalization Score based on Topic overlap
                p_score = 0.0
                tags = meta.get('tags', [])
                for tag in tags:
                    # Session intent is weighted highest (0.5), then short (0.3), then long (0.2)
                    topic_score = (
                        0.5 * session.get(tag, 0.0) +
                        0.3 * short_term.get(tag, 0.0) +
                        0.2 * long_term.get(tag, 0.0)
                    )
                    
                    # Heavy penalty for negative topics
                    if tag in negative:
                        topic_score -= negative[tag] * 2.0
                        
                    p_score += topic_score
                
                # Base rank score: 200 for 1st, 1 for 200th
                try:
                    base_rank_score = 200 - top_content_keys.index(content_key) 
                except ValueError:
                    base_rank_score = 1
                
                # Creator Quality Score (0-100)
                c_score = creator_scores.get(meta['creator_id'], 50.0) # default 50
                
                # Base heuristic score: 50% personalization, 30% global popularity, 20% creator quality
                heuristic_score = (0.5 * p_score * 100) + (0.3 * base_rank_score) + (0.2 * c_score)
                
                # Apply Phase 3: Deep Ranker + Satisfaction predictor
                final_score = ranker.score_candidate(
                    user_features={'profile': profile}, 
                    content_features=meta, 
                    base_score=heuristic_score
                )
                
                scored_candidates.append((final_score, meta))

            # 4. Sort by final score
            scored_candidates.sort(key=lambda x: x[0], reverse=True)
            
            # 5. Apply Phase 3: MMR Diversity and fatigue limits
            feed_items = apply_mmr(scored_candidates, lambda_param=0.3, max_consecutive_creator=2)
            
            # Trim to max total size across all pages
            max_feed_items = FEED_SIZE * NUM_PAGES
            feed_items = feed_items[:max_feed_items]
            
            # 6. Apply Phase 4: Bandit Exploration Slots (Task 12)
            # Replace some items with random/new exploration items if available
            import random
            exploration_pool = [c for c in top_content_keys if c[1] not in seen_content_ids and content_meta.get(c) not in feed_items]
            if len(exploration_pool) >= 2 and len(feed_items) > 5:
                # Pick 2 items for exploration
                exp_items = random.sample(exploration_pool, min(2, len(exploration_pool)))
                # Tag them so the client/events know they are exploration
                for idx, exp_key in enumerate(exp_items):
                    meta = content_meta.get(exp_key)
                    if meta:
                        meta['is_exploration'] = True
                        # Insert at positions 3 and 7 (roughly)
                        insert_pos = 3 if idx == 0 else min(7, len(feed_items))
                        feed_items.insert(insert_pos, meta)
                
                feed_items = feed_items[:max_feed_items]

            # If not enough unseen content, pad with top content (allow re-shows)
            if len(feed_items) < max_feed_items:
                for content_key in top_content_keys:
                    meta = content_meta.get(content_key)
                    if meta and meta not in feed_items:
                        feed_items.append(meta)
                    if len(feed_items) >= max_feed_items:
                        break

            # Write to Redis, paginated
            for page in range(1, NUM_PAGES + 1):
                start_idx = (page - 1) * FEED_SIZE
                end_idx = start_idx + FEED_SIZE
                page_items = feed_items[start_idx:end_idx]
                
                if page_items:
                    feed_key = f'feed:{user_id}:page:{page}'
                    r.set(feed_key, json.dumps(page_items), ex=FEED_TTL_SECONDS)
                    
            feeds_built += 1

        except Exception as e:
            logger.error(f'Failed to build feed for user {user_id}: {e}')
            continue

    logger.info(f'rebuild_user_feeds: built {feeds_built} feeds for {len(active_user_ids)} active users.')
    return {'feeds_built': feeds_built}

"""
Feature Store Sync Tasks
========================
Periodic task to sync user interaction events into their multi-horizon
interest profiles.

Updates are written to MySQL (source of truth) and Redis (fast online reads).
"""

import json
import logging
from datetime import timedelta

import redis
from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import UserInterestProfile
from .services import update_interest_vectors

logger = logging.getLogger(__name__)


def _get_cache_redis():
    """Get Redis connection for the online feature store (DB 3)."""
    return redis.Redis.from_url(
        settings.REDIS_CACHE_URL,
        decode_responses=True,
    )

@shared_task(name='api.modules.feature_store.tasks.sync_user_features')
def sync_user_features():
    """
    Celery Beat task (e.g. every 10 mins).
    
    1. Finds users with new events since their profile was last updated.
    2. Fetches their new events and content tags.
    3. Updates their long/short/session/negative interest vectors.
    4. Writes to MySQL AND mirrors to Redis `profile:{user_id}`.
    """
    from api.modules.rec_events.models import RecEvent
    from api.models import Reel, Post
    
    now = timezone.now()
    
    # We'll process users who had events in the last hour
    cutoff = now - timedelta(hours=1)
    
    active_users = list(
        RecEvent.objects.filter(timestamp__gte=cutoff, is_flagged=False)
        .values_list('user_id', flat=True).distinct()
    )
    
    if not active_users:
        logger.info("sync_user_features: no active users to sync.")
        return {'users_synced': 0}
        
    r = _get_cache_redis()
    synced_count = 0
    
    for user_id in active_users:
        try:
            profile, _ = UserInterestProfile.objects.get_or_create(user_id=user_id)
            
            # Get events since this profile was last updated (or all recent if new)
            last_update = profile.updated_at or cutoff
            # subtract 1 min to avoid missing edge cases
            last_update = last_update - timedelta(minutes=1)
            
            events = list(
                RecEvent.objects.filter(
                    user_id=user_id,
                    timestamp__gte=last_update,
                    is_flagged=False
                ).order_by('-timestamp')
            )
            
            if not events:
                continue
                
            # Pre-fetch content tags for these events
            content_ids = [e.content_id for e in events]
            
            reel_tags = Reel.objects.filter(id__in=content_ids).prefetch_related('hashtags')
            post_tags = Post.objects.filter(id__in=content_ids).prefetch_related('hashtags')
            
            tag_lookup = {}
            for reel in reel_tags:
                tag_lookup[reel.id] = [tag.name.lower() for tag in reel.hashtags.all()]
            for post in post_tags:
                tag_lookup[post.id] = [tag.name.lower() for tag in post.hashtags.all()]
                
            from api.modules.ranking.taxonomy import expand_tags
            from api.modules.feature_store.models import UserInterestEntity
            
            # Decay existing scores: -5% per day since last_interacted_at
            # This satisfies the "Score Decay" requirement
            existing_entities = UserInterestEntity.objects.filter(user_id=user_id)
            for entity in existing_entities:
                days_since = (now - entity.last_interacted_at).days
                if days_since > 0:
                    decay_factor = (0.95 ** days_since)
                    entity.interest_score = entity.interest_score * decay_factor
                    entity.last_interacted_at = now
                    entity.save()

            for event in events:
                raw_topics = tag_lookup.get(event.content_id, [])
                # Apply hierarchical topic modeling (e.g. m4 -> bmw -> cars)
                topics = expand_tags(raw_topics)
                
                event_type = event.event_type
                watch_pct = event.watch_pct
                
                # Apply specific blueprint math for scoring
                weight = 0.0
                if event_type == 'watch':
                    if watch_pct and watch_pct >= 0.95:
                        weight = 0.15
                    elif watch_pct and watch_pct >= 0.50:
                        weight = 0.10
                elif event_type == 'like':
                    weight = 0.10
                elif event_type == 'save':
                    weight = 0.15
                elif event_type == 'share':
                    weight = 0.20
                elif event_type == 'follow':
                    weight = 0.15
                elif event_type in ('not_interested', 'hide'):
                    weight = -0.50
                elif event_type == 'skip':
                    weight = -0.10
                    
                if weight == 0.0:
                    continue
                    
                is_positive = weight > 0
                is_negative = weight < 0

                for topic in topics:
                    entity, created = UserInterestEntity.objects.get_or_create(
                        user_id=user_id,
                        entity_type='CATEGORY',
                        entity_id=topic,
                    )
                    
                    # Accumulate score based on the raw blueprint logic
                    entity.interest_score += weight
                    # Bound it between 0 and 1.0 if we want it to strictly match 0.96 scale,
                    # but capping at 1.0 might lose relative strengths. We'll let it grow 
                    # but naturally decay, or we can cap it at 1.0. Let's cap at 1.0 for simplicity.
                    entity.interest_score = min(max(entity.interest_score, 0.0), 1.0)
                    
                    if is_positive:
                        entity.positive_count += 1
                    elif is_negative:
                        entity.negative_count += 1
                    
                    entity.last_interacted_at = now
                    entity.save()
            
            # --- PHASE 3: Social & Creator Affinity Updates ---
            from api.modules.feature_store.models import UserSocialAffinity, UserCreatorAffinity
            
            for event in events:
                # 1. Creator Affinity
                if event.creator_id and event.creator_id != user_id:
                    # Give points for engaging with creator's content or profile
                    c_weight = 0.0
                    if event.event_type in ('watch', 'like', 'save', 'share', 'comment'):
                        c_weight = 0.10
                    elif event.event_type == 'follow':
                        c_weight = 0.50
                    elif event.event_type == 'profile_view' and event.content_type == 'profile':
                        c_weight = 0.20
                        
                    if c_weight > 0:
                        c_affinity, _ = UserCreatorAffinity.objects.get_or_create(
                            user_id=user_id, creator_id=event.creator_id
                        )
                        c_affinity.affinity_score += c_weight
                        c_affinity.interaction_count += 1
                        c_affinity.last_interaction_at = now
                        c_affinity.save()
                
                # 2. Social Affinity
                # For social interactions, target_user is usually passed in content_id or device_context
                target_user_id = None
                if event.content_type == 'profile' and event.content_id:
                    target_user_id = event.content_id
                elif event.event_type in ('message', 'tag', 'mention', 'message_from_social_card', 'friend_request_sent'):
                    # Assume target is passed in device_context for MVP
                    target_user_id = event.device_context.get('target_user_id')
                elif event.event_type in ('profile_card_open', 'social_reaction', 'tagged_in_reel'):
                    target_user_id = event.device_context.get('target_user_id') or event.creator_id
                    
                if target_user_id and target_user_id != user_id:
                    s_weight = 0.0
                    if event.event_type == 'friend_request_sent':
                        s_weight = 0.80  # Very Strong
                    elif event.event_type in ('message', 'message_from_social_card'):
                        s_weight = 0.50  # Strong signal
                    elif event.event_type in ('tag', 'mention', 'tagged_in_reel'):
                        s_weight = 0.40
                    elif event.event_type == 'social_reaction':
                        s_weight = 0.30
                    elif event.event_type in ('profile_view', 'profile_card_open'):
                        s_weight = 0.20
                        
                    if s_weight > 0:
                        s_affinity, _ = UserSocialAffinity.objects.get_or_create(
                            user_id=user_id, target_user_id=target_user_id
                        )
                        s_affinity.affinity_score += s_weight
                        s_affinity.interaction_count += 1
                        s_affinity.last_interaction_at = now
                        s_affinity.save()
            # ------------------------------------------------
            
            # Serialize the Top 50 interests into a flat JSON dictionary for Redis
            top_interests = UserInterestEntity.objects.filter(
                user_id=user_id, entity_type='CATEGORY', interest_score__gt=0
            ).order_by('-interest_score')[:50]
            
            redis_interests = {entity.entity_id: entity.interest_score for entity in top_interests}
            
            # Cache into Redis for ultra-low latency recommendation assembly
            r.set(f"user:{user_id}:interests", json.dumps(redis_interests))
            
            # Also update legacy UserInterestProfile for backwards compatibility
            profile.updated_at = now
            profile.save()
            
            synced_count += 1
            
        except Exception as e:
            logger.error(f"Failed to sync features for user {user_id}: {e}")
            
    logger.info(f"sync_user_features: synced {synced_count} profiles.")
    return {'users_synced': synced_count}

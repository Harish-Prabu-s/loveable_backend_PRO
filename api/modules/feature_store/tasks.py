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
            
            # Since content could be Reels or Posts, we query both and extract hashtags
            # In a real app we'd query the Content table directly.
            reel_tags = Reel.objects.filter(id__in=content_ids).prefetch_related('hashtags')
            post_tags = Post.objects.filter(id__in=content_ids).prefetch_related('hashtags')
            
            tag_lookup = {}
            for reel in reel_tags:
                tag_lookup[reel.id] = [tag.name.lower() for tag in reel.hashtags.all()]
            for post in post_tags:
                tag_lookup[post.id] = [tag.name.lower() for tag in post.hashtags.all()]
                
            # Attach topics to events
            event_dicts = []
            for event in events:
                topics = tag_lookup.get(event.content_id, [])
                event_dicts.append({
                    'event_type': event.event_type,
                    'watch_pct': event.watch_pct,
                    'session_id': event.session_id,
                    'topics': topics
                })
                
            # Update the profile (in-memory)
            profile = update_interest_vectors(profile, event_dicts, now=now)
            
            # Save to MySQL
            profile.save()
            
            # Mirror to Redis
            profile_data = {
                'long_term': profile.long_term,
                'short_term': profile.short_term,
                'session': profile.session,
                'negative_confidence': profile.negative_confidence
            }
            r.set(f"profile:{user_id}", json.dumps(profile_data))
            
            synced_count += 1
            
        except Exception as e:
            logger.error(f"Failed to sync features for user {user_id}: {e}")
            
    logger.info(f"sync_user_features: synced {synced_count} profiles.")
    return {'users_synced': synced_count}

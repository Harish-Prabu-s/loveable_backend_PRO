"""
Seen Filter
===========
Manages user seen-history in Redis for ultra-fast filtering during candidate generation.
A Bloom Filter could be used here for massive scale, but a Redis Set per user
with a TTL is sufficient and exact for MVP.
"""
from django.conf import settings
import redis

# Redis connection for seen state (can be same as cache or separate DB)
_redis = redis.Redis.from_url(
    settings.REDIS_CACHE_URL, 
    decode_responses=True
)

SEEN_TTL = 60 * 60 * 24 * 7  # 7 days

def mark_as_seen(user_id: int, content_id: int):
    """Marks a single item as seen."""
    key = f"seen:{user_id}"
    _redis.sadd(key, content_id)
    _redis.expire(key, SEEN_TTL)

def mark_multiple_as_seen(user_id: int, content_ids: list):
    """Marks multiple items as seen."""
    if not content_ids:
        return
    key = f"seen:{user_id}"
    _redis.sadd(key, *content_ids)
    _redis.expire(key, SEEN_TTL)

def get_seen_items(user_id: int) -> set:
    """Returns the set of seen item IDs for the user."""
    key = f"seen:{user_id}"
    members = _redis.smembers(key)
    return {int(x) for x in members}

def filter_unseen(user_id: int, candidates: list) -> list:
    """Filters a list of candidate IDs, returning only unseen ones."""
    seen = get_seen_items(user_id)
    return [c for c in candidates if c not in seen]

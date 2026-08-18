"""
Anti-Abuse Pre-Filter
=====================
Analyzes incoming recommendation events to detect and drop bot/spam
activity before it pollutes the feature store or ranking models.
"""

from datetime import timedelta
from django.utils import timezone
from django.core.cache import cache

def is_event_suspicious(user_id: int, event_type: str, timestamp) -> bool:
    """
    Checks if a given event from a user matches known abuse patterns.
    Currently checks for:
    - Burst liking (> 20 likes in 10 seconds)
    
    Returns True if suspicious, False otherwise.
    """
    if event_type == 'like':
        # Track like rate
        cache_key = f"abuse:like_rate:{user_id}"
        # Get current count, default 0
        try:
            count = cache.incr(cache_key)
        except ValueError:
            # Key doesn't exist
            cache.set(cache_key, 1, timeout=10)
            count = 1
            
        if count > 20:
            return True
            
    # Watch percentage sanity checks can also be added here,
    # e.g. watching 100% of a 60s video in 2s of wall-clock time
    # This requires stateful tracking of when the video started playing.
    
    return False

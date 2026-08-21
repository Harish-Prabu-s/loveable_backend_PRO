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
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=10)
            count = 1
            
        if count > 20:
            return True
            
    if event_type == 'skip':
        # Track skip rate
        cache_key = f"abuse:skip_rate:{user_id}"
        try:
            count = cache.incr(cache_key)
        except ValueError:
            cache.set(cache_key, 1, timeout=10)
            count = 1
            
        # If someone skips 30 videos in 10 seconds, it's likely a bot or mindless swiping
        # This will flag the events so they don't corrupt the negative interest vectors
        if count > 30:
            return True
            
    if event_type in ('watch', 'rewatch', 'rewatch_complete'):
        # Watch time sanity check: if watch_pct is very high but the time between 
        # events from this user is physically impossible, flag it.
        # This is a simplified check; a true check needs the video length.
        cache_key = f"abuse:last_watch_time:{user_id}"
        last_time = cache.get(cache_key)
        now_ts = timezone.now().timestamp()
        
        cache.set(cache_key, now_ts, timeout=600)
        
        if last_time:
            time_diff = now_ts - last_time
            # If they supposedly watched a video to completion but the events are < 1s apart
            # it's likely API abuse or a bug.
            # (Assuming most videos are > 3 seconds)
            if time_diff < 1.0:
                return True
                
    return False

"""
Session Boundary Detector
=========================
Helper logic to manage user sessions. A session is defined as a contiguous
period of activity without a gap larger than SESSION_TIMEOUT_MINUTES.

This would typically be called during event ingestion or as a periodic cleanup task
to flush finished sessions into the SessionLog table.
"""

from datetime import timedelta
from django.utils import timezone
import uuid
import logging
from django.core.cache import cache
from .tasks import _flush_session

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_MINUTES = 30

def get_or_create_session(user_id: int, event_timestamp=None) -> str:
    """
    Returns the active session_id for a user. If they have been inactive
    for longer than the timeout, a new session is generated.
    """
    if event_timestamp is None:
        event_timestamp = timezone.now()
        
    cache_key = f"user_session_tracker:{user_id}"
    session_data = cache.get(cache_key)
    
    if session_data:
        last_activity = session_data['last_activity']
        session_id = session_data['session_id']
        
        # Check if the gap is larger than timeout
        if (event_timestamp - last_activity) > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
            # Session expired, flush the old one (async) and create new
            _flush_session.delay(user_id, session_id)
            session_id = str(uuid.uuid4())
            
    else:
        # No active session
        session_id = str(uuid.uuid4())
        
    # Update last activity. Set timeout to 7 days so we don't lose the session tracking
    # before we have a chance to flush it on their next visit.
    cache.set(cache_key, {
        'session_id': session_id,
        'last_activity': event_timestamp
    }, timeout=86400 * 7)
    
    return session_id

def log_session_end(user_id: int, session_id: str):
    """
    Called when a session formally ends to summarize and log it.
    """
    _flush_session.delay(user_id, session_id)


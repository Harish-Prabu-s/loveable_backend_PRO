"""
Feature Store Services
======================
Logic for parsing tags/topics from content and updating the
multi-horizon interest vectors using Exponential Moving Average (EMA).
"""

import math
from datetime import timedelta
from collections import defaultdict
from django.utils import timezone
from api.modules.ranking.services import EVENT_WEIGHTS

# Decay constants (half-lives in hours)
DECAY_HOURS = {
    'long_term': 14 * 24, # 14 days
    'short_term': 48,     # 48 hours
}

def decay_vector(vector: dict, age_hours: float, half_life_hours: float) -> dict:
    """
    Decays values in a topic vector based on how much time has passed.
    """
    if not vector or half_life_hours <= 0:
        return vector
        
    decay_factor = math.exp(-0.693 * age_hours / half_life_hours)
    
    decayed = {}
    for topic, weight in vector.items():
        new_weight = weight * decay_factor
        # Prune very small weights
        if new_weight > 0.01:
            decayed[topic] = new_weight
            
    return decayed

def update_interest_vectors(profile, recent_events, now=None):
    """
    Update the user's interest vectors (long, short, session, negative)
    based on new events since the last update.
    
    `profile` is a UserInterestProfile instance.
    `recent_events` is a list of RecEvent dicts (must include content tags).
    """
    if now is None:
        now = timezone.now()
        
    # Calculate how much time passed since last update for decay
    age_hours = 0.0
    if profile.updated_at:
        age_hours = (now - profile.updated_at).total_seconds() / 3600.0
        
    # 1. Apply decay to existing vectors
    long_term = decay_vector(profile.long_term, age_hours, DECAY_HOURS['long_term'])
    short_term = decay_vector(profile.short_term, age_hours, DECAY_HOURS['short_term'])
    
    # Session decays fully if session_id changed, or not at all (managed by session detector)
    session = profile.session.copy()
    
    negative = profile.negative_confidence.copy()
    # Negative confidence also decays but very slowly (e.g. 30 days) to allow forgiveness
    negative = decay_vector(negative, age_hours, 30 * 24)

    # 2. Aggregate new event signals by topic
    # We expect events to have a 'topics' list (joined from Content tags)
    topic_signals = defaultdict(float)
    
    for event in recent_events:
        event_type = event['event_type']
        topics = event.get('topics', [])
        
        weight = EVENT_WEIGHTS.get(event_type, 0.0)
        if event_type in ('watch', 'replay'):
            weight *= max(event.get('watch_pct', 0.0), 0.1)
            
        for topic in topics:
            topic_signals[topic] += weight

    # 3. Apply EMA updates to vectors
    # EMA formula: new_vector = (1 - alpha) * old_vector + alpha * signal
    
    alpha_long = 0.05
    alpha_short = 0.20
    alpha_session = 0.50
    alpha_neg = 0.30

    for topic, signal in topic_signals.items():
        if signal > 0:
            # Positive interest
            long_term[topic] = (1 - alpha_long) * long_term.get(topic, 0.0) + (alpha_long * signal)
            short_term[topic] = (1 - alpha_short) * short_term.get(topic, 0.0) + (alpha_short * signal)
            session[topic] = (1 - alpha_session) * session.get(topic, 0.0) + (alpha_session * signal)
        elif signal < 0:
            # Explicit negative feedback (not_interested, hide)
            # Use abs(signal) to increase negative confidence
            neg_signal = abs(signal)
            negative[topic] = (1 - alpha_neg) * negative.get(topic, 0.0) + (alpha_neg * neg_signal)
            
            # Penalize existing positive vectors heavily
            if topic in long_term:
                long_term[topic] *= 0.5
            if topic in short_term:
                short_term[topic] *= 0.2
            if topic in session:
                session[topic] *= 0.1

    # Normalize vectors so they represent a probability distribution (sum to 1) 
    # or just cap them to avoid explosive growth
    def cap_vector(v):
        for k in v:
            v[k] = min(v[k], 10.0) # Arbitrary cap to prevent runaway weights
        return v
        
    profile.long_term = cap_vector(long_term)
    profile.short_term = cap_vector(short_term)
    profile.session = cap_vector(session)
    profile.negative_confidence = cap_vector(negative)
    
    # Track latest session ID
    if recent_events:
        # Get the session_id from the latest event
        latest_session = recent_events[0].get('session_id')
        if latest_session and latest_session != profile.last_session_id:
            profile.last_session_id = latest_session
            # If session changed, clear session vector
            profile.session = {}

    return profile

"""
UserInterestProfile Model
=========================
Stores the user's multi-horizon interest profile as defined in the masterplan
Section 3. This serves as the offline (source-of-truth) copy of the features.

A Celery task (`sync_user_features`) computes this from recent events and writes
it here AND mirrors it to Redis for low-latency online serving.
"""

from django.db import models
from django.contrib.auth.models import User


class UserInterestProfile(models.Model):
    """
    Multi-horizon interest profile for a user.

    long_term: decays slowly over weeks. Captures core interests.
    short_term: decays over ~48h. Captures recent rabbit-holes.
    session: resets on new session_id or decays rapidly.
    negative_confidence: explicitly 'not interested' or hidden topics.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='interest_profile'
    )
    
    # Store topic weights (e.g. {"technology": 0.90, "comedy": 0.15})
    long_term = models.JSONField(default=dict, blank=True)
    short_term = models.JSONField(default=dict, blank=True)
    session = models.JSONField(default=dict, blank=True)
    
    # Topics user explicitly disliked or skipped repeatedly
    negative_confidence = models.JSONField(default=dict, blank=True)
    
    # The session ID these features were last updated under
    last_session_id = models.UUIDField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"InterestProfile for User {self.user_id}"

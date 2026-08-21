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


class UserInterestEntity(models.Model):
    """
    Stores granular, row-based interest tracking per user and per entity.
    An 'entity' can be a CATEGORY (topic), a CREATOR, a BRAND, or a TAG.

    This enables analytical SQL queries like 'find all users highly interested in cars'
    or 'find all users with high creator affinity for user X', which is hard to do
    with the JSON-based UserInterestProfile.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='interest_entities'
    )
    entity_type = models.CharField(
        max_length=20, 
        choices=(
            ('CATEGORY', 'Category'),
            ('CREATOR', 'Creator'),
            ('BRAND', 'Brand'),
            ('TAG', 'Tag')
        ),
        db_index=True
    )
    # The unique identifier for the entity (e.g. topic string or creator_id)
    entity_id = models.CharField(max_length=100, db_index=True)
    
    # Accumulated interest score (e.g. decayed sum of positive engagements)
    interest_score = models.FloatField(default=0.0, db_index=True)
    
    # Raw engagement counts
    positive_count = models.IntegerField(default=0)
    negative_count = models.IntegerField(default=0)
    
    last_interacted_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'entity_type', 'entity_id')
        indexes = [
            models.Index(fields=['user', 'entity_type', '-interest_score']),
            models.Index(fields=['entity_type', 'entity_id', '-interest_score']),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.entity_type}:{self.entity_id} ({self.interest_score:.2f})"

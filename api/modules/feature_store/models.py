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


class UserSocialAffinity(models.Model):
    """
    Blueprint §5. Tracks computed affinity score and interaction counts between two users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_affinities')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='targeted_by_affinities')
    
    affinity_score = models.DecimalField(max_digits=6, decimal_places=4, default=0, db_index=True)
    message_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    profile_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    content_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    comment_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    tag_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    follow_score = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    
    interaction_count = models.IntegerField(default=0)
    last_interaction_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'target_user')
        indexes = [
            models.Index(fields=['user', '-affinity_score']),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.target_user_id} (Score: {self.affinity_score})"


class SocialDiscoveryEvent(models.Model):
    """
    Blueprint §2.6 / §5. Durable log of why a user became interested in another user.
    """
    actor_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discovery_events_initiated')
    target_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discovery_events_received')
    
    source_type = models.CharField(max_length=40, help_text="e.g. REEL_LIKER, COMMENTER, FLOATING_PROFILE")
    source_content_id = models.PositiveBigIntegerField(null=True, blank=True)
    surface = models.CharField(max_length=40, help_text="e.g. FLOATING_PROFILE, COMMENT_SECTION")
    event_type = models.CharField(max_length=40)
    
    INTERACTION_STRENGTH_CHOICES = (
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('STRONG', 'Strong'),
        ('VERY_STRONG', 'Very Strong'),
    )
    interaction_strength = models.CharField(max_length=20, choices=INTERACTION_STRENGTH_CHOICES, default='LOW')
    interaction_score = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    
    session_id = models.CharField(max_length=64, null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['actor_user', 'target_user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.actor_user_id} discovered {self.target_user_id} via {self.source_type}"


class ProfileViewEvent(models.Model):
    """
    Blueprint §2.6 / §5.5. Tracks profile view sources.
    """
    viewer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profile_views_made')
    profile_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='profile_views_received')
    
    source_type = models.CharField(max_length=40, help_text="e.g. REEL, POST, SEARCH, FLOATING_PROFILE")
    source_content_id = models.PositiveBigIntegerField(null=True, blank=True)
    source_user_id = models.PositiveBigIntegerField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['viewer_user', 'profile_user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.viewer_user_id} viewed {self.profile_user_id} via {self.source_type}"


class UserCreatorAffinity(models.Model):
    """
    Stores the relationship strength between a user and a content creator.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='creator_affinities')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='creator_affinities_target')
    
    affinity_score = models.FloatField(default=0.0, db_index=True)
    interaction_count = models.IntegerField(default=0)
    last_interaction_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'creator')
        indexes = [
            models.Index(fields=['user', '-affinity_score']),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.creator_id} (Creator) ({self.affinity_score:.2f})"

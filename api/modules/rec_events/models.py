"""
RecEvent Model
==============
Stores every user action in the recommendation event log.
Matches the Event schema from the masterplan (Section 3).

Key design decisions:
- event_id is a UUID primary key (client-generated) for idempotency — re-sending
  the same event_id is a no-op, not a duplicate row.
- Indexed on (user_id, content_id, timestamp) for efficient querying by the
  popularity/CF/feature-store Celery tasks.
- device_context is a JSONField for flexible client-side metadata without
  needing schema migrations for every new field.
"""

import uuid
from django.db import models
from django.contrib.auth.models import User


class RecEvent(models.Model):
    """
    A single user interaction event for the recommendation engine.

    Matches masterplan Section 3 Event schema exactly:
    event_id, user_id, content_id, creator_id, event_type, watch_pct,
    session_id, timestamp, source, device_context.
    """

    EVENT_TYPE_CHOICES = (
        ('watch', 'Watch'),
        ('replay', 'Replay'),
        ('like', 'Like'),
        ('save', 'Save'),
        ('share', 'Share'),
        ('comment', 'Comment'),
        ('follow', 'Follow'),
        ('skip', 'Skip'),
        ('not_interested', 'Not Interested'),
        ('hide', 'Hide'),
        ('report', 'Report'),
        # Rewatch / revisit event types (Blueprint §5-§8)
        ('revisit', 'Revisit'),                    # User scrolled back to previously seen content
        ('rewatch', 'Rewatch'),                    # User actively watches previously seen content again
        ('rewatch_complete', 'Rewatch Complete'),  # User completes a rewatch
        ('navigation_back', 'Navigation Back'),    # Neutral backward scroll navigation
        # Master Tracking Events
        ('impression_start', 'Impression Start'),
        ('progress', 'Progress'),
        ('loop', 'Loop'),
        ('impression_end', 'Impression End'),
        # Social & Unified Tracking Events
        ('profile_view', 'Profile View'),
        ('search', 'Search'),
        ('message', 'Message'),
        ('tag', 'Tag'),
        ('mention', 'Mention'),
    )

    SOURCE_CHOICES = (
        ('feed', 'Feed'),
        ('search', 'Search'),
        ('profile', 'Profile'),
        ('explore', 'Explore'),
    )

    # UUID primary key — client-generated for idempotent re-delivery
    event_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Who did what to which content
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='rec_events',
        db_index=True,
    )
    content_id = models.PositiveBigIntegerField(
        db_index=True, null=True, blank=True,
        help_text='ID of the Reel/Post/Content this event refers to.',
    )
    CONTENT_TYPE_CHOICES = (
        ('reel', 'Reel'),
        ('post', 'Post'),
        ('profile', 'Profile'),
        ('search_query', 'Search Query'),
    )
    content_type = models.CharField(
        max_length=20, choices=CONTENT_TYPE_CHOICES, default='reel',
        db_index=True,
        help_text='The type of content (reel, post, profile, search).',
    )
    creator_id = models.PositiveBigIntegerField(
        null=True, blank=True,
        help_text='ID of the content creator (denormalized for fast queries).',
    )

    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES)
    watch_pct = models.FloatField(
        default=0.0,
        help_text='Fraction of content watched (0.0 to 1.0). Only meaningful for watch/replay events.',
    )

    # Session tracking
    session_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text='Overall app session ID (legacy).',
    )
    play_session_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text='One per continuous engagement with a single reel.',
    )
    feed_session_id = models.UUIDField(
        null=True, blank=True, db_index=True,
        help_text='Links multiple views in one continuous feed scroll.',
    )

    timestamp = models.DateTimeField(db_index=True)

    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='feed',
    )

    device_context = models.JSONField(
        default=dict, blank=True,
        help_text='Flexible client metadata: time_of_day, platform, etc.',
    )

    # Master Tracking Plan Fields
    watch_ms = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='Total time spent watching during this event.',
    )
    loop_index = models.PositiveSmallIntegerField(
        default=0,
        help_text='Increments per in-session Loop/Replay.',
    )
    scroll_direction = models.CharField(
        max_length=10, null=True, blank=True,
        help_text='Direction scrolled (up or down).',
    )

    # Granular watch milestones (Blueprint §2 event pipeline)
    milestones = models.JSONField(
        default=list, blank=True,
        help_text='Array of granular milestones crossed, e.g. ["play_start", "2s", "25%", "50%"].',
    )

    # Abuse flagging (Task 13 will use this)
    is_flagged = models.BooleanField(
        default=False, db_index=True,
        help_text='True if this event was flagged by the anti-abuse pre-filter.',
    )

    class Meta:
        # Composite index for the most common query patterns:
        indexes = [
            models.Index(fields=['user', 'content_type', 'content_id', 'timestamp'],
                         name='idx_recev_user_ctype_cid_ts'),
            models.Index(fields=['user', 'timestamp'],
                         name='idx_recevent_user_ts'),
            models.Index(fields=['content_type', 'content_id', 'timestamp'],
                         name='idx_recev_ctype_cid_ts'),
        ]
        ordering = ['-timestamp']

    def __str__(self):
        return f'{self.event_type} by user {self.user_id} on content {self.content_id}'


class SessionLog(models.Model):
    """
    Aggregated metrics for a single user session.
    A session is bounded by 30 minutes of inactivity.
    """
    session_id = models.UUIDField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='session_logs')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    
    total_events = models.IntegerField(default=0)
    avg_watch_pct = models.FloatField(default=0.0)
    skip_rate = models.FloatField(default=0.0)
    not_interested_count = models.IntegerField(default=0)
    
    # Pre-computed satisfaction for this session for analytics
    satisfaction_score = models.FloatField(default=0.0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Precomputed aggregates
    total_reels_watched = models.IntegerField(default=0)
    total_reels_skipped = models.IntegerField(default=0)
    total_watch_time_sec = models.IntegerField(default=0)
    total_likes = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    total_shares = models.IntegerField(default=0)

    # Re-engagement metric: True if user returned after >12 hours of inactivity
    is_reengagement_session = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['user', '-start_time']),
        ]
        ordering = ['-start_time']

    def __str__(self):
        return f"Session {self.session_id} for user {self.user_id}"


class ReelViewSession(models.Model):
    """
    Aggregated viewing session for a single content piece.
    Created when an impression ends, summarizing all raw events (watch, loop, backward, etc).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reel_view_sessions')
    content_id = models.PositiveBigIntegerField(db_index=True)
    content_type = models.CharField(max_length=20, default='reel', db_index=True)
    
    play_session_id = models.UUIDField(unique=True, help_text='Links to raw RecEvents for this viewing session')
    feed_session_id = models.UUIDField(null=True, blank=True, db_index=True, help_text='Links multiple views in one continuous feed scroll')
    
    max_watch_percent = models.FloatField(default=0.0)
    total_watch_ms = models.PositiveIntegerField(default=0)
    loop_count = models.PositiveSmallIntegerField(default=0)
    
    SESSION_OUTCOMES = (
        ('QUICK_SKIP', 'Quick Skip (<15%)'),
        ('PARTIAL_SKIP', 'Partial Skip (15-70%)'),
        ('NORMAL_EXIT', 'Normal Exit (70-99%)'),
        ('COMPLETED', 'Completed (>=99%)'),
        ('REWATCH_EXIT', 'Rewatch Exit'),
    )
    session_outcome = models.CharField(max_length=20, choices=SESSION_OUTCOMES)
    is_meaningful_view = models.BooleanField(default=False, db_index=True)
    
    started_at = models.DateTimeField(db_index=True)
    ended_at = models.DateTimeField()
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'content_type', 'content_id']),
            models.Index(fields=['feed_session_id', 'started_at']),
        ]
        ordering = ['-started_at']

    def __str__(self):
        return f"View {self.play_session_id} outcome: {self.session_outcome}"


class UserContentInterest(models.Model):
    """
    Aggregate tracking model per user+content pair (Master Plan §2.2).
    Provides fast reads for UI badges ('Watched', 'Rewatched') without counting raw events.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='content_interests')
    content_id = models.PositiveBigIntegerField(db_index=True)
    content_type = models.CharField(max_length=20, default='reel')
    
    # Quantitative metrics
    impression_count = models.PositiveSmallIntegerField(default=0)
    view_session_count = models.PositiveSmallIntegerField(default=0)
    meaningful_view_count = models.PositiveSmallIntegerField(default=0)
    completed_count = models.PositiveSmallIntegerField(default=0)
    rewatch_count = models.PositiveSmallIntegerField(default=0)
    quick_skip_count = models.PositiveSmallIntegerField(default=0)
    partial_skip_count = models.PositiveSmallIntegerField(default=0)
    
    # Qualitative metrics
    max_watch_percent = models.FloatField(default=0.0)
    total_watch_ms = models.PositiveIntegerField(default=0)
    last_watch_percent = models.FloatField(default=0.0)
    
    last_action = models.CharField(max_length=50, blank=True, null=True, db_index=True)
    
    first_seen_at = models.DateTimeField(null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'content_id', 'content_type')
        indexes = [
            models.Index(fields=['user', 'content_type', 'last_action']),
            models.Index(fields=['user', 'last_seen_at']),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.content_type}:{self.content_id} ({self.last_action})"

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
        db_index=True,
        help_text='ID of the Reel/Post/Content this event refers to.',
    )
    CONTENT_TYPE_CHOICES = (
        ('reel', 'Reel'),
        ('post', 'Post'),
    )
    content_type = models.CharField(
        max_length=10, choices=CONTENT_TYPE_CHOICES, default='reel',
        db_index=True,
        help_text='The type of content (reel or post).',
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
        help_text='Client-assigned session ID. Used for session-interest vector.',
    )

    timestamp = models.DateTimeField(db_index=True)

    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default='feed',
    )

    device_context = models.JSONField(
        default=dict, blank=True,
        help_text='Flexible client metadata: time_of_day, platform, etc.',
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
    
    class Meta:
        indexes = [
            models.Index(fields=['user', '-start_time']),
        ]
        ordering = ['-start_time']

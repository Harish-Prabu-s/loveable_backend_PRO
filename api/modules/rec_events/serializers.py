"""
Event Serializers
=================
DRF serializer for ingesting user interaction events.

Validates all fields against the masterplan Section 3 Event schema before
the event is pushed onto the Redis Stream. Rejects malformed events with
a 400 at the DRF layer so they never enter the pipeline.
"""

from rest_framework import serializers


class RecEventSerializer(serializers.Serializer):
    """
    Validates incoming event payloads.

    This is a plain Serializer (not ModelSerializer) because events go to
    the Redis Stream first, not directly to MySQL. The Celery consumer
    handles persistence.
    """

    VALID_EVENT_TYPES = {
        'watch', 'replay', 'like', 'save', 'share', 'comment',
        'follow', 'skip', 'not_interested', 'hide', 'report',
        # Rewatch / revisit event types (Blueprint §5-§8)
        'revisit', 'rewatch', 'rewatch_complete', 'navigation_back',
        # Master Tracking Events
        'impression_start', 'progress', 'loop', 'impression_end',
        # Social & Unified Tracking Events
        'profile_view', 'search', 'message', 'tag', 'mention',
        'profile_card_open', 'social_reaction', 'message_from_social_card',
        'tagged_in_reel', 'friend_request_sent',
        # Impressions
        'impression_shown',
    }
    VALID_SOURCES = {'feed', 'search', 'profile', 'explore', 'reel_liker'}
    VALID_CONTENT_TYPES = {'reel', 'post', 'profile', 'search_query'}

    event_id = serializers.UUIDField(required=True)
    content_id = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    content_type = serializers.CharField(required=False, default='reel', max_length=20)
    creator_id = serializers.IntegerField(required=False, min_value=1, allow_null=True)
    event_type = serializers.CharField(required=True, max_length=20)
    watch_pct = serializers.FloatField(required=False, default=0.0)
    session_id = serializers.UUIDField(required=False, allow_null=True)
    play_session_id = serializers.UUIDField(required=False, allow_null=True)
    feed_session_id = serializers.UUIDField(required=False, allow_null=True)
    timestamp = serializers.DateTimeField(required=True)
    source = serializers.CharField(required=False, default='feed', max_length=20)
    
    # Master Tracking Fields
    watch_ms = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    loop_index = serializers.IntegerField(required=False, min_value=0, default=0)
    scroll_direction = serializers.CharField(required=False, max_length=10, allow_null=True)
    
    # Impression/Feedback Loop Fields
    candidate_source = serializers.CharField(required=False, max_length=50, allow_null=True)
    position = serializers.IntegerField(required=False, allow_null=True)
    source_user_id = serializers.IntegerField(required=False, min_value=1, allow_null=True)

    device_context = serializers.DictField(required=False, default=dict)
    # Granular milestones (Blueprint §2): e.g. ['play_start', '2s', '25%', '50%', '75%', '100%']
    milestones = serializers.ListField(
        child=serializers.CharField(max_length=20),
        required=False, default=list,
    )

    def validate_event_type(self, value):
        if value not in self.VALID_EVENT_TYPES:
            raise serializers.ValidationError(
                f'Invalid event_type "{value}". '
                f'Must be one of: {", ".join(sorted(self.VALID_EVENT_TYPES))}'
            )
        return value

    def validate_watch_pct(self, value):
        if value < 0.0 or value > 1.0:
            raise serializers.ValidationError(
                'watch_pct must be between 0.0 and 1.0.'
            )
        return value

    def validate_source(self, value):
        if value not in self.VALID_SOURCES:
            raise serializers.ValidationError(
                f'Invalid source "{value}". '
                f'Must be one of: {", ".join(sorted(self.VALID_SOURCES))}'
            )
        return value

    def validate_content_type(self, value):
        if value not in self.VALID_CONTENT_TYPES:
            raise serializers.ValidationError(
                f'Invalid content_type "{value}". '
                f'Must be one of: {", ".join(sorted(self.VALID_CONTENT_TYPES))}'
            )
        return value

    def validate(self, data):
        """Cross-field validation."""
        event_type = data.get('event_type')
        watch_pct = data.get('watch_pct', 0.0)

        # watch_pct is meaningful for watch, replay, rewatch, and rewatch_complete events
        WATCH_LIKE_EVENTS = ('watch', 'replay', 'rewatch', 'rewatch_complete')
        if event_type in WATCH_LIKE_EVENTS and watch_pct == 0.0:
            # Allow 0.0 (user opened but immediately closed), but warn
            pass

        # Non-watch events should not have a meaningful watch_pct
        if event_type not in WATCH_LIKE_EVENTS and watch_pct > 0.0:
            data['watch_pct'] = 0.0  # Silently zero it out

        return data

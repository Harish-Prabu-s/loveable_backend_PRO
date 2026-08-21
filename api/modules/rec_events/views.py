"""
Event Ingestion Views
=====================
POST /api/rec/events/ — accepts user interaction events, validates via the
DRF serializer, pushes them onto a Redis Stream for async processing.

The endpoint returns 202 (Accepted) on success because the event is queued
for processing, not immediately written to MySQL.

Rate limiting: uses DRF's built-in throttling with a per-user burst limit
to prevent event flooding.
"""

import json
import logging

import redis
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .serializers import RecEventSerializer

logger = logging.getLogger(__name__)


class EventBurstThrottle(UserRateThrottle):
    """Per-user burst rate limit for event ingestion.
    100 events per second per user — generous for normal use,
    catches runaway clients or replay attacks.
    """
    rate = '100/second'


# Lazy-initialized Redis connection for the Streams DB
_stream_redis = None


def _get_stream_redis():
    """Get or create the Redis connection for Streams (DB 2)."""
    global _stream_redis
    if _stream_redis is None:
        _stream_redis = redis.Redis.from_url(
            settings.REDIS_STREAMS_URL,
            decode_responses=True,
        )
    return _stream_redis


class EventIngestView(APIView):
    """
    POST /api/rec/events/

    Accepts a single event matching the masterplan Section 3 Event schema.
    Validates the payload, then pushes it onto the Redis Stream `user-events`
    for the Celery consumer to process.

    Returns:
        202 Accepted — event queued for processing
        400 Bad Request — malformed event (validation errors in body)
        429 Too Many Requests — rate limit exceeded
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [EventBurstThrottle]

    def post(self, request):
        serializer = RecEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data
        
        # ── Phase 3: Session Boundary Detector ──
        from .session_detector import get_or_create_session
        client_session = str(validated.get('session_id') or '')
        # If client provided one, use it, but still touch the cache to keep it alive
        # Otherwise, assign one automatically
        session_id = get_or_create_session(
            request.user.id, 
            event_timestamp=validated['timestamp']
        )
        if client_session:
            session_id = client_session

        # Build the stream message — all values must be strings for Redis Streams
        stream_message = {
            'event_id': str(validated['event_id']),
            'user_id': str(request.user.id),
            'content_id': str(validated.get('content_id') or ''),
            'content_type': validated.get('content_type', 'reel'),
            'creator_id': str(validated.get('creator_id') or ''),
            'event_type': validated['event_type'],
            'watch_pct': str(validated.get('watch_pct', 0.0)),
            'session_id': session_id,
            'play_session_id': str(validated.get('play_session_id') or ''),
            'feed_session_id': str(validated.get('feed_session_id') or ''),
            'watch_ms': str(validated.get('watch_ms') or ''),
            'loop_index': str(validated.get('loop_index', 0)),
            'scroll_direction': str(validated.get('scroll_direction') or ''),
            'candidate_source': str(validated.get('candidate_source') or ''),
            'position': str(validated.get('position') or ''),
            'source_user_id': str(validated.get('source_user_id') or ''),
            'timestamp': validated['timestamp'].isoformat(),
            'source': validated.get('source', 'feed'),
            'device_context': json.dumps(validated.get('device_context', {})),
            'milestones': json.dumps(validated.get('milestones', [])),
        }

        try:
            r = _get_stream_redis()
            # XADD to the user-events stream with auto-generated ID
            # MAXLEN ~ 100000 keeps the stream bounded (approximate trimming)
            r.xadd('user-events', stream_message, maxlen=100000, approximate=True)
        except redis.RedisError as e:
            logger.error(f'Failed to push event to Redis Stream: {e}')
            return Response(
                {'error': 'Event queue temporarily unavailable. Please retry.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'status': 'accepted', 'event_id': str(validated['event_id'])},
            status=status.HTTP_202_ACCEPTED,
        )


class EventBatchIngestView(APIView):
    """
    POST /api/rec/events/batch/

    Accepts a list of events for batch ingestion (e.g. when the client
    comes back online after being offline). Same validation per event.

    Body: {"events": [ ... array of event objects ... ]}

    Returns:
        202 Accepted — all events queued
        400 Bad Request — at least one event is malformed (returns first error)
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [EventBurstThrottle]

    def post(self, request):
        events = request.data.get('events', [])
        if not isinstance(events, list) or len(events) == 0:
            return Response(
                {'error': 'Request body must contain a non-empty "events" array.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(events) > 100:
            return Response(
                {'error': 'Maximum 100 events per batch.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Validate all events first — fail fast on any invalid one
        validated_events = []
        for i, event_data in enumerate(events):
            serializer = RecEventSerializer(data=event_data)
            if not serializer.is_valid():
                return Response(
                    {'error': f'Event at index {i} is invalid.',
                     'details': serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            validated_events.append(serializer.validated_data)

        # All valid — push to Redis Stream
        try:
            r = _get_stream_redis()
            pipe = r.pipeline()
            from .session_detector import get_or_create_session
            
            for validated in validated_events:
                client_session = str(validated.get('session_id') or '')
                session_id = get_or_create_session(
                    request.user.id, 
                    event_timestamp=validated['timestamp']
                )
                if client_session:
                    session_id = client_session
                    
                stream_message = {
                    'event_id': str(validated['event_id']),
                    'user_id': str(request.user.id),
                    'content_id': str(validated.get('content_id') or ''),
                    'content_type': validated.get('content_type', 'reel'),
                    'creator_id': str(validated.get('creator_id') or ''),
                    'event_type': validated['event_type'],
                    'watch_pct': str(validated.get('watch_pct', 0.0)),
                    'session_id': session_id,
                    'play_session_id': str(validated.get('play_session_id') or ''),
                    'feed_session_id': str(validated.get('feed_session_id') or ''),
                    'watch_ms': str(validated.get('watch_ms') or ''),
                    'loop_index': str(validated.get('loop_index', 0)),
                    'scroll_direction': str(validated.get('scroll_direction') or ''),
                    'candidate_source': str(validated.get('candidate_source') or ''),
                    'position': str(validated.get('position') or ''),
                    'source_user_id': str(validated.get('source_user_id') or ''),
                    'timestamp': validated['timestamp'].isoformat(),
                    'source': validated.get('source', 'feed'),
                    'device_context': json.dumps(validated.get('device_context', {})),
                    'milestones': json.dumps(validated.get('milestones', [])),
                }
                pipe.xadd('user-events', stream_message, maxlen=100000, approximate=True)
            pipe.execute()
        except redis.RedisError as e:
            logger.error(f'Failed to push batch events to Redis Stream: {e}')
            return Response(
                {'error': 'Event queue temporarily unavailable. Please retry.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'status': 'accepted', 'count': len(validated_events)},
            status=status.HTTP_202_ACCEPTED,
        )

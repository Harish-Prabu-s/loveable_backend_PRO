import json
import logging
import redis
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .views import EventBurstThrottle, _get_stream_redis
from .social_serializers import SocialEventSerializer

logger = logging.getLogger(__name__)

class SocialEventIngestView(APIView):
    """
    POST /api/rec/social-events/
    
    Accepts a single social event matching the masterplan Section 5.3 schema.
    Pushes it to the Redis Stream `social-events`.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [EventBurstThrottle]

    def post(self, request):
        serializer = SocialEventSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'errors': serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        validated = serializer.validated_data

        stream_message = {
            'event_id': str(validated['event_id']),
            'event_type': validated['event_type'],
            'actor_user_id': str(request.user.id),
            'target_user_id': str(validated['target_user_id']),
            'source': json.dumps(validated['source']),
            'context': json.dumps(validated.get('context', {})),
            'interaction': json.dumps(validated['interaction']),
            'feed_session_id': str(validated.get('feed_session_id') or ''),
            'timestamp': validated['timestamp'].isoformat(),
        }

        try:
            r = _get_stream_redis()
            r.xadd('social-events', stream_message, maxlen=100000, approximate=True)
        except redis.RedisError as e:
            logger.error(f'Failed to push social event to Redis Stream: {e}')
            return Response(
                {'error': 'Event queue temporarily unavailable. Please retry.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {'status': 'accepted', 'event_id': str(validated['event_id'])},
            status=status.HTTP_202_ACCEPTED,
        )

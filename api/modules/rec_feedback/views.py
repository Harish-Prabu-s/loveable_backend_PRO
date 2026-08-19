"""
Feedback Endpoints
==================
Endpoints for explicit user feedback on recommendations.
These actions write directly to the event stream or modify the user's profile.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from api.modules.rec_events.views import _get_stream_redis
import json
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ExplicitFeedbackView(APIView):
    """
    POST /api/rec/feedback/
    
    Accepts feedback actions: 'not_interested', 'show_more', 'hide_creator', 'hide_topic'.
    For 'not_interested' and 'show_more', we just fire an event into the stream,
    and the feature store takes care of it.
    
    Body:
    {
        "action": "not_interested" | "show_more" | "hide_creator" | "hide_topic",
        "content_id": 123,
        "creator_id": 45 (optional, required for hide_creator),
        "topic": "comedy" (optional, required for hide_topic)
    }
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        action = request.data.get('action')
        content_id = request.data.get('content_id')
        
        if not action or action not in ['not_interested', 'show_more', 'hide_creator', 'hide_topic']:
            return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)
            
        event_type = 'not_interested'
        if action == 'show_more':
            event_type = 'like' # Alias to like for simplicity
        elif action == 'hide_creator':
            event_type = 'hide'
            if not request.data.get('creator_id'):
                return Response({'error': 'creator_id required'}, status=status.HTTP_400_BAD_REQUEST)
        elif action == 'hide_topic':
            event_type = 'hide'
            if not request.data.get('topic'):
                return Response({'error': 'topic required'}, status=status.HTTP_400_BAD_REQUEST)
                
        # Send event to stream
        stream_message = {
            'event_id': str(uuid.uuid4()),
            'user_id': str(request.user.id),
            'content_id': str(content_id or 0),
            'creator_id': str(request.data.get('creator_id') or ''),
            'event_type': event_type,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'feedback_menu',
            'device_context': json.dumps({'topic': request.data.get('topic')})
        }
        
        try:
            r = _get_stream_redis()
            r.xadd('user-events', stream_message, maxlen=100000, approximate=True)
            return Response({'status': 'feedback_recorded'})
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            return Response({'error': 'Service unavailable'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class WhyAmISeeingThisView(APIView):
    """
    GET /api/rec/feedback/why/?content_id=123
    
    Returns a human-readable explanation of why a post was recommended.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        content_id = request.query_params.get('content_id')
        if not content_id:
            return Response({'error': 'content_id required'}, status=status.HTTP_400_BAD_REQUEST)
            
        # In a fully fleshed out system, this would query the ContentScore and UserInterestProfile
        # to find the overlapping vectors or the CF neighbor that caused the match.
        # MVP placeholder logic:
        return Response({
            'reasons': [
                "Because you've liked similar content recently.",
                "This post is currently popular among people with similar interests."
            ]
        })

class ResetRecommendationsView(APIView):
    """
    POST /api/rec/feedback/reset/
    
    Clears the user's interest profile so they can start fresh.
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from api.modules.feature_store.models import UserInterestProfile
        try:
            UserInterestProfile.objects.filter(user=request.user).delete()
            # Also clear redis cache
            from api.modules.feature_store.tasks import _get_cache_redis
            r = _get_cache_redis()
            r.delete(f"profile:{request.user.id}")
            r.delete(f"feed:{request.user.id}")
            return Response({'status': 'recommendations_reset'})
        except Exception as e:
            logger.error(f"Failed to reset recommendations: {e}")
            return Response({'error': 'Failed to reset'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class InterestsView(APIView):
    """
    GET /api/rec/feedback/interests/
    DELETE /api/rec/feedback/interests/<topic>/
    
    Allows users to view and delete their tracked interests.
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from api.modules.feature_store.models import UserInterestProfile
        try:
            profile = UserInterestProfile.objects.get(user=request.user)
            # Combine long_term and short_term
            interests_dict = profile.long_term or {}
            
            # Format for frontend
            interests = []
            for topic, weight in interests_dict.items():
                interests.append({
                    'id': topic,
                    'topic': topic.title(),
                    'weight': weight
                })
            
            # Sort by weight descending
            interests.sort(key=lambda x: x['weight'], reverse=True)
            return Response({'interests': interests})
        except UserInterestProfile.DoesNotExist:
            return Response({'interests': []})
            
    def delete(self, request, topic=None):
        if not topic:
            return Response({'error': 'topic required'}, status=status.HTTP_400_BAD_REQUEST)
            
        from api.modules.feature_store.models import UserInterestProfile
        try:
            profile = UserInterestProfile.objects.get(user=request.user)
            
            # Remove from all profiles
            if profile.long_term and topic in profile.long_term:
                del profile.long_term[topic]
            if profile.short_term and topic in profile.short_term:
                del profile.short_term[topic]
            if profile.session and topic in profile.session:
                del profile.session[topic]
                
            # Add to negative confidence so it doesn't get re-added easily
            if not profile.negative_confidence:
                profile.negative_confidence = {}
            profile.negative_confidence[topic] = 1.0
            
            profile.save()
            
            # Clear redis cache
            from api.modules.feature_store.tasks import _get_cache_redis
            r = _get_cache_redis()
            r.delete(f"profile:{request.user.id}")
            
            return Response({'status': 'interest_removed'})
        except UserInterestProfile.DoesNotExist:
            return Response({'status': 'interest_removed'}) # Already doesn't exist

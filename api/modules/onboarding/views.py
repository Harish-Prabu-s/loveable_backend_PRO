import json
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from api.modules.feature_store.models import UserInterestProfile, UserInterestEntity

class OnboardingInterestsView(APIView):
    """
    POST /api/onboarding/interests/
    Accepts a list of topic categories chosen by the user during onboarding
    and primes their UserInterestProfile and UserInterestEntity to solve cold start.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        topics = request.data.get('topics', [])
        
        if not isinstance(topics, list) or not topics:
            return Response(
                {"error": "Please provide a list of topics."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Clean topics
        topics = [str(t).lower().strip() for t in topics]
        
        # 1. Update the JSON profile (Long term interests)
        profile, _ = UserInterestProfile.objects.get_or_create(user_id=request.user.id)
        
        # Give them a strong initial weight (e.g. 5.0)
        current_long = profile.long_term or {}
        for topic in topics:
            current_long[topic] = current_long.get(topic, 0) + 5.0
            
        profile.long_term = current_long
        profile.save()
        
        # 2. Update the Entity rows for analytical querying
        for topic in topics:
            entity, created = UserInterestEntity.objects.get_or_create(
                user_id=request.user.id,
                entity_type='CATEGORY',
                entity_id=topic,
            )
            entity.interest_score += 5.0
            entity.positive_count += 1
            entity.save()
            
        # 3. Force a sync to Redis for immediate feed generation
        try:
            from api.modules.feature_store.tasks import _get_cache_redis
            r = _get_cache_redis()
            profile_data = {
                'long_term': profile.long_term,
                'short_term': profile.short_term,
                'session': profile.session,
                'negative_confidence': profile.negative_confidence
            }
            r.set(f"profile:{request.user.id}", json.dumps(profile_data))
        except Exception as e:
            # Non-fatal if cache fails
            pass
            
        return Response({"status": "success", "topics_saved": len(topics)})

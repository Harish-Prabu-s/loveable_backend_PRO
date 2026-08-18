from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

class PrivacyConsentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        """
        Records the user's consent for recommendation personalization.
        """
        consent = request.data.get('consent', False)
        
        # Save to user profile (mocked for MVP)
        # request.user.profile.rec_consent_given = consent
        # request.user.profile.save()
        
        # If consent is withdrawn, we should also trigger the reset logic
        if not consent:
            from api.modules.feature_store.models import UserInterestProfile
            from django.core.cache import cache
            
            UserInterestProfile.objects.filter(user_id=request.user.id).delete()
            cache.delete(f'profile:{request.user.id}')
            
        return Response({'status': 'consent updated', 'consent': consent})

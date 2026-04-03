from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework import status
from api.models import MonetizationRule
from .serializers import MonetizationRuleSerializer
from .services import get_cost, is_night_time, seed_default_rules


class MonetizationRuleListView(APIView):
    """GET: list all rules (any authenticated user).
       POST: create a rule (admin only)."""

    def get(self, request):
        seed_default_rules()  # ensure defaults exist
        rules = MonetizationRule.objects.filter(is_active=True).order_by('action_type')
        return Response(MonetizationRuleSerializer(rules, many=True).data)

    def post(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=status.HTTP_403_FORBIDDEN)
        ser = MonetizationRuleSerializer(data=request.data)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)


class MonetizationRuleDetailView(APIView):
    """PATCH / PUT / DELETE a specific rule (admin only)."""

    def get_object(self, pk):
        try:
            return MonetizationRule.objects.get(pk=pk)
        except MonetizationRule.DoesNotExist:
            return None

    def get(self, request, pk):
        rule = self.get_object(pk)
        if not rule:
            return Response({'detail': 'Not found.'}, status=404)
        return Response(MonetizationRuleSerializer(rule).data)

    def patch(self, request, pk):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)
        rule = self.get_object(pk)
        if not rule:
            return Response({'detail': 'Not found.'}, status=404)
        ser = MonetizationRuleSerializer(rule, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=400)

    def delete(self, request, pk):
        if not request.user.is_staff:
            return Response({'detail': 'Admin only.'}, status=403)
        rule = self.get_object(pk)
        if not rule:
            return Response({'detail': 'Not found.'}, status=404)
        rule.delete()
        return Response(status=204)


class PricingLookupView(APIView):
    """GET /api/monetization/pricing/?action=audio_call
    Returns the effective cost (day or night) for a given action."""

    FIELD_MAP = {
        'audio_call': 'cost_per_minute',
        'video_call': 'cost_per_minute',
        'live':       'cost_per_minute',
        'chat':       'cost_per_message',
        'photo':      'cost_per_media',
        'video_msg':  'cost_per_media',
        'bet_match':  'cost_per_media',
        'gift':       'cost_per_media',
    }

    def get(self, request):
        action = request.query_params.get('action')
        if not action or action not in self.FIELD_MAP:
            return Response({'detail': 'Invalid or missing action parameter.'}, status=400)
        field = self.FIELD_MAP[action]
        cost  = get_cost(action, field)
        return Response({
            'action': action,
            'cost':   cost,
            'is_night': is_night_time(),
        })

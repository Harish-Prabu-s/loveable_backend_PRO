from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from api.models import BetMatch
from .serializers import BetMatchSerializer
from .services import create_bet_match, join_bet_match, declare_result


class CreateBetMatchView(APIView):
    """POST /api/betmatch/create/ — create or auto-join a bet match."""

    def post(self, request):
        try:
            match = create_bet_match(request.user)
            return Response(BetMatchSerializer(match).data, status=201)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)


class JoinBetMatchView(APIView):
    """POST /api/betmatch/join/<id>/ — female user joins specific match."""

    def post(self, request, match_id):
        try:
            match = join_bet_match(match_id, request.user)
            return Response(BetMatchSerializer(match).data)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)


class BetMatchResultView(APIView):
    """POST /api/betmatch/result/<id>/ — declare winner (admin or participant)."""

    def post(self, request, match_id):
        winner_gender = request.data.get('winner_gender')
        if winner_gender not in ('M', 'F'):
            return Response({'detail': "winner_gender must be 'M' or 'F'."}, status=400)

        try:
            match = BetMatch.objects.get(pk=match_id)
        except BetMatch.DoesNotExist:
            return Response({'detail': 'Match not found.'}, status=404)

        # Only participants or admins can declare result
        is_participant = (match.male_user == request.user or match.female_user == request.user)
        if not is_participant and not request.user.is_staff:
            return Response({'detail': 'Forbidden.'}, status=403)

        try:
            match = declare_result(match_id, winner_gender)
            return Response(BetMatchSerializer(match).data)
        except ValueError as e:
            return Response({'detail': str(e)}, status=400)


class BetMatchListView(APIView):
    """GET /api/betmatch/list/?status=pending|active|completed"""

    def get(self, request):
        status_filter = request.query_params.get('status', 'pending')
        matches = BetMatch.objects.filter(status=status_filter).order_by('-created_at')[:30]
        return Response(BetMatchSerializer(matches, many=True).data)

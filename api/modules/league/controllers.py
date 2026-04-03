from rest_framework.views import APIView
from rest_framework.response import Response
from api.models import LeagueStats
from django.contrib.auth.models import User


RANK_FIELD_MAP = {
    'coins':            '-total_coins_earned',
    'money':            '-total_money_earned',
    'call_duration':    '-total_call_seconds',
    'calls_received':   '-total_calls_received',
    'time_spent':       '-total_time_seconds',
    'bet_wins':         '-bet_match_wins',
}


def _serialize_entry(stats, rank):
    user = stats.user
    try:
        profile = user.profile
        display_name = profile.display_name
        photo = str(profile.photo) if profile.photo else None
        gender = profile.gender
        is_online = profile.is_online
    except Exception:
        display_name = user.username
        photo = None
        gender = None
        is_online = False
    return {
        'rank':               rank,
        'user_id':            user.id,
        'display_name':       display_name,
        'photo':              photo,
        'gender':             gender,
        'is_online':          is_online,
        'total_coins_earned': stats.total_coins_earned,
        'total_money_earned': str(stats.total_money_earned),
        'total_call_seconds': stats.total_call_seconds,
        'total_calls_received': stats.total_calls_received,
        'total_time_seconds': stats.total_time_seconds,
        'bet_match_wins':     stats.bet_match_wins,
    }


class LeaderboardView(APIView):
    """GET /api/league/leaderboard/?rank_by=coins|money|call_duration|calls_received|time_spent|bet_wins"""

    def get(self, request):
        rank_by = request.query_params.get('rank_by', 'coins')
        order_field = RANK_FIELD_MAP.get(rank_by, '-total_coins_earned')
        top_stats = LeagueStats.objects.select_related('user__profile').order_by(order_field)[:100]
        data = [_serialize_entry(s, i + 1) for i, s in enumerate(top_stats)]
        return Response({'rank_by': rank_by, 'results': data})


class MyRankView(APIView):
    """GET /api/league/my-rank/?rank_by=coins — returns the logged-in user's rank."""

    def get(self, request):
        rank_by = request.query_params.get('rank_by', 'coins')
        order_field = RANK_FIELD_MAP.get(rank_by, '-total_coins_earned')

        try:
            my_stats = LeagueStats.objects.get(user=request.user)
        except LeagueStats.DoesNotExist:
            return Response({'rank': None, 'detail': 'No stats yet.'})

        # Count how many users rank above me
        field_name = order_field.lstrip('-')
        my_value = getattr(my_stats, field_name)
        rank = LeagueStats.objects.filter(**{f'{field_name}__gt': my_value}).count() + 1
        return Response(_serialize_entry(my_stats, rank))

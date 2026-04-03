from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...serializers import LevelProgressSerializer, DailyRewardSerializer
from .services import get_user_level, list_daily_rewards, claim_daily_reward, leaderboard
from ...serializers import ProfileSerializer
from ...models import Profile

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def level_view(request):
    lp = get_user_level(request.user)
    return Response(LevelProgressSerializer(lp).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_rewards_view(request):
    qs = list_daily_rewards(request.user)
    return Response(DailyRewardSerializer(qs, many=True).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def claim_daily_reward_view(request, day: int):
    dr = claim_daily_reward(request.user, day)
    if not dr:
        return Response({'error': 'invalid day'}, status=400)
    return Response(DailyRewardSerializer(dr).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def leaderboard_view(request):
    qs = leaderboard()
    results = []
    rank = 1
    for lp in qs:
        profile = Profile.objects.get(user=lp.user)
        results.append({
            'user': {
                'id': lp.user.id,
                'phone_number': profile.phone_number,
                'gender': profile.gender,
                'is_verified': profile.is_verified,
                'is_online': profile.is_online,
                'date_joined': profile.date_joined.isoformat(),
                'last_login': profile.last_login.isoformat() if profile.last_login else None,
            },
            'profile': ProfileSerializer(profile).data,
            'xp': lp.xp,
            'level': lp.level,
            'rank': rank,
        })
        rank += 1
    return Response({
        'count': len(results),
        'next': None,
        'previous': None,
        'results': results,
    })

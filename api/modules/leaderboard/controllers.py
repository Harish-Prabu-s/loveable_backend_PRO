from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..gamification.services import get_streak_leaderboard_service, get_call_time_leaderboard_service
from ...serializers import ProfileSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streak_leaderboard_view(request):
    # Optimized service now returns User queryset with select_related('profile')
    users = get_streak_leaderboard_service()
    data = []
    for i, user in enumerate(users):
        p = getattr(user, 'profile', None)
        data.append({
            'rank': i + 1,
            'user_id': user.id,
            'username': user.username,
            'display_name': p.display_name if p else user.username,
            'profile_pic': p.photo.url if p and p.photo else None,
            'streak_count': user.streak_count
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def video_call_leaderboard_view(request):
    users = get_call_time_leaderboard_service('VIDEO')
    data = []
    for i, user in enumerate(users):
        p = getattr(user, 'profile', None)
        data.append({
            'rank': i + 1,
            'user_id': user.id,
            'username': user.username,
            'display_name': p.display_name if p else user.username,
            'profile_pic': p.photo.url if p and p.photo else None,
            'total_duration': user.total_duration
        })
    return Response(data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audio_call_leaderboard_view(request):
    users = get_call_time_leaderboard_service('VOICE')
    data = []
    for i, user in enumerate(users):
        p = getattr(user, 'profile', None)
        data.append({
            'rank': i + 1,
            'user_id': user.id,
            'username': user.username,
            'display_name': p.display_name if p else user.username,
            'profile_pic': p.photo.url if p and p.photo else None,
            'total_duration': user.total_duration
        })
    return Response(data)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def total_call_leaderboard_view(request):
    users = get_call_time_leaderboard_service('ALL')
    data = []
    for i, user in enumerate(users):
        p = getattr(user, 'profile', None)
        data.append({
            'rank': i + 1,
            'user_id': user.id,
            'username': user.username,
            'display_name': p.display_name if p else user.username,
            'profile_pic': p.photo.url if p and p.photo else None,
            'total_duration': user.total_duration
        })
    return Response(data)

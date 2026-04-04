from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import upload_streak_service, get_user_streaks_service, add_streak_comment, get_streak_comments, get_streak_upload_service

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def upload_streak(request):
    media = request.FILES.get('media')
    if not media:
        return Response({'error': 'media is required'}, status=400)
    
    media_type = request.data.get('media_type', 'image')
    visibility = request.data.get('visibility', 'all')
    caption = request.data.get('caption', '').strip()
    
    upload, msg = upload_streak_service(request.user, media, media_type, visibility, caption)
    if not upload:
        return Response({'error': msg}, status=400)
    
    return Response({'status': msg, 'id': upload.id})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_streaks(request):
    data = get_user_streaks_service(request.user, request)
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_comment(request, upload_id):
    text = request.data.get('text')
    if not text:
        return Response({'error': 'text is required'}, status=400)
    
    comment = add_streak_comment(upload_id, request.user, text)
    if not comment:
        return Response({'error': 'Comment could not be added'}, status=400)
    
    return Response({'status': 'Comment added', 'id': comment.id})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_comments(request, upload_id):
    comments = get_streak_comments(upload_id)
    if comments is None:
        return Response({'error': 'Streak not found'}, status=404)
    
    from ...serializers import ProfileSerializer
    return Response([{
        'id': c.id,
        'user': ProfileSerializer(c.user.profile, context={'request': request}).data,
        'text': c.text,
        'created_at': c.created_at
    } for c in comments])
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_streak_upload(request, upload_id):
    upload = get_streak_upload_service(upload_id)
    if not upload:
        return Response({'error': 'Streak upload not found'}, status=404)
    
    from ...serializers import ProfileSerializer
    from ...utils import get_absolute_media_url
    
    return Response({
        'id': upload.id,
        'user': ProfileSerializer(upload.user.profile, context={'request': request}).data,
        'media_url': get_absolute_media_url(upload.media_url, request),
        'media_type': upload.media_type,
        'visibility': upload.visibility,
        'created_at': upload.created_at
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_streaks_snapchat(request):
    view_type = request.query_params.get('type', 'friends')
    from .services import get_streaks_list_service
    data = get_streaks_list_service(request.user, view_type, request)
    return Response(data)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, upload_id):
    from .services import toggle_streak_like
    liked, msg = toggle_streak_like(upload_id, request.user)
    if liked is None:
        return Response({'error': msg}, status=404)
    return Response({'status': msg, 'liked': liked})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_fire(request, upload_id):
    from .services import toggle_streak_reaction
    fired, msg, count, fire_count = toggle_streak_reaction(upload_id, request.user, 'fire')
    if fired is None:
        return Response({'error': msg}, status=404)
    return Response({'status': msg, 'fired': fired, 'streak_count': count, 'fire_count': fire_count})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_user_fire(request, user_id):
    from .services import toggle_user_fire_service
    fired, msg, count, fire_count = toggle_user_fire_service(user_id, request.user)
    if fired is None:
        return Response({'error': msg}, status=404)
    return Response({'status': msg, 'fired': fired, 'streak_count': count, 'fire_count': fire_count})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streak_leaderboard_view(request):
    try:
        from django.contrib.auth.models import User
        from django.db.models import Count, Q, Max, F
        from django.db.models.functions import Greatest
        from ...utils import get_absolute_media_url
        
        # Rank users by total received fire reactions
        # Also get their highest streak count safely
        users = User.objects.annotate(
            fire_count=Count('received_reactions', filter=Q(received_reactions__reaction_type='fire')),
            max_s1=Max('streaks_user1__streak_count'),
            max_s2=Max('streaks_user2__streak_count'),
            upload_count=Count('streak_uploads')
        ).annotate(
            best_streak=Greatest(F('max_s1'), F('max_s2'), default=0)
        ).filter(Q(fire_count__gt=0) | Q(best_streak__gt=0) | Q(upload_count__gt=0)).order_by('-fire_count', '-best_streak')[:50]
        
        data = []
        for u in users:
            profile = getattr(u, 'profile', None)
            photo_url = get_absolute_media_url(profile.photo.url, request) if profile and profile.photo else None
            
            data.append({
                'user_id': u.id,
                'username': u.username,
                'display_name': profile.display_name if profile else u.username,
                'photo': photo_url,
                'fire_count': u.fire_count,
                'streak_count': u.best_streak,
            })
        return Response(data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in streak_leaderboard_view: {e}")
        return Response({'error': str(e)}, status=400)

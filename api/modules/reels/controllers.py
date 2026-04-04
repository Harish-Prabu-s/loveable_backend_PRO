from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from ...serializers import ReelSerializer
from .services import (
    list_reels, create_reel, toggle_reel_like, add_reel_comment,
    get_reel_comments, share_reel_to_chat, delete_reel_service
)
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from ...utils import strip_base_url
import uuid
import os

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_reels_view(request):
    try:
        page = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 10))
    except ValueError:
        page, limit = 1, 10
        
    random_flag = request.GET.get('random', 'false').lower() == 'true'
    
    qs = list_reels(user=request.user, limit=limit, page=page, random_flag=random_flag)
    return Response(ReelSerializer(qs, many=True, context={'request': request}).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_reel_media_view(request):
    try:
        if 'media' not in request.FILES:
            return Response({'error': 'media file required'}, status=400)
        
        file = request.FILES['media']
        fs = FileSystemStorage(location=settings.MEDIA_ROOT / 'reels', base_url=settings.MEDIA_URL + 'reels/')
        
        ext = os.path.splitext(file.name)[1].lower() or '.mp4'
        safe_filename = f"{request.user.id}_{uuid.uuid4().hex}{ext}"
        
        filename = fs.save(safe_filename, file)
        url = request.build_absolute_uri(fs.url(filename))
        return Response({'url': url}, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_reel_view(request):
    video_url = request.data.get('video_url')
    caption = request.data.get('caption', '')
    visibility = request.data.get('visibility', 'all')
    if not video_url:
        return Response({'error': 'video_url required'}, status=400)
    
    # Ensure we store relative path in DB
    relative_video_path = strip_base_url(video_url)
    
    reel = create_reel(request.user, relative_video_path, caption, visibility)
    return Response(ReelSerializer(reel, context={'request': request}).data, status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_reel_view(request, pk):
    result = toggle_reel_like(pk, request.user)
    if result is None:
        return Response({'error': 'Reel not found'}, status=404)
    
    # Notification logic
    if result.get('liked'):
        reel = result['reel']
        if reel.user != request.user:
            from ..notifications.push_service import send_push_notification, _get_user_tokens
            from ..notifications.services import create_notification
            tokens = _get_user_tokens(reel.user.id)
            profile = getattr(request.user, 'profile', None)
            sender_name = profile.display_name if profile else request.user.username
            
            # Persist to DB
            create_notification(
                recipient=reel.user,
                actor=request.user,
                notification_type='reel_like',
                message=f"{sender_name} liked your reel!",
                object_id=reel.id
            )

            if tokens:
                send_push_notification(
                    tokens, 
                    title="New Like!", 
                    body=f"{sender_name} liked your reel!",
                    data={'type': 'reel_like', 'reel_id': reel.id}
                )

    return Response({'liked': result['liked'], 'likes_count': result['likes_count']})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_reel_view(request, pk):
    text = request.data.get('text')
    if not text:
        return Response({'error': 'text required'}, status=400)
    
    comment = add_reel_comment(pk, request.user, text)
    if comment is None:
        return Response({'error': 'Reel not found'}, status=404)

    # Notification logic
    reel = comment.reel
    if reel.user != request.user:
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        from ..notifications.services import create_notification
        tokens = _get_user_tokens(reel.user.id)
        profile = getattr(request.user, 'profile', None)
        sender_name = profile.display_name if profile else request.user.username
        
        # Persist to DB
        create_notification(
            recipient=reel.user,
            actor=request.user,
            notification_type='reel_comment',
            message=f"{sender_name} commented: {text[:30]}...",
            object_id=reel.id
        )

        if tokens:
            send_push_notification(
                tokens, 
                title="New Comment!", 
                body=f"{sender_name} commented: {text[:30]}...",
                data={'type': 'reel_comment', 'reel_id': reel.id}
            )

    return Response({'success': True, 'id': comment.id})

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_comments_view(request, pk: int):
    if request.method == 'POST':
        return comment_reel_view(request._request, pk)
    comments = get_reel_comments(pk)
    if comments is None:
        return Response({'error': 'Reel not found'}, status=404)
    
    data = []
    from ...utils import get_absolute_media_url
    for c in comments:
        p = getattr(c.user, 'profile', None)
        data.append({
            'id': c.id,
            'user': c.user.id,
            'display_name': p.display_name if p else '',
            'photo': get_absolute_media_url(p.photo, request) if p and p.photo else None,
            'text': c.text,
            'created_at': c.created_at.isoformat(),
        })
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def share_reel_view(request, pk: int):
    target_user_id = request.data.get('target_user_id')
    if not target_user_id:
        return Response({'error': 'target_user_id required'}, status=400)
    
    result = share_reel_to_chat(pk, request.user, target_user_id)
    if result is None:
        return Response({'error': 'reel or user not found'}, status=404)

    # Notification logic
    target_user = result['target_user']
    reel = result['reel']
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    from ..notifications.services import create_notification
    tokens = _get_user_tokens(target_user.id)
    profile = getattr(request.user, 'profile', None)
    sender_name = profile.display_name if profile else request.user.username
    
    # Persist to DB
    create_notification(
        recipient=target_user,
        actor=request.user,
        notification_type='reel_share',
        message=f"{sender_name} shared a reel with you.",
        object_id=reel.id
    )

    if tokens:
        send_push_notification(
            tokens, 
            title="Shared Reel", 
            body=f"{sender_name} shared a reel with you.",
            data={'type': 'reel_share', 'reel_id': reel.id, 'from_user_id': request.user.id}
        )
    
    return Response({'success': True})

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_reel_view(request, pk: int):
    result = delete_reel_service(pk, request.user)
    if 'error' in result:
        return Response({'error': result['error']}, status=result['status'])
    return Response(status=204)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def repost_reel_view(request, pk: int):
    from .services import repost_reel
    reel = repost_reel(request.user, pk)
    if not reel:
        return Response({'error': 'reel not found'}, status=404)
    return Response(ReelSerializer(reel, context={'request': request}).data, status=201)

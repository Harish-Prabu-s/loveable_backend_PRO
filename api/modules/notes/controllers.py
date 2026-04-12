from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from ...models import Note, Audio


def _note_data(note, request):
    from ...utils import get_absolute_media_url
    audio_url = get_absolute_media_url(note.audio.file_url, request) if note.audio else None
    avatar_url = None
    if hasattr(note.user, 'profile') and note.user.profile.photo:
        avatar_url = get_absolute_media_url(note.user.profile.photo, request)
    return {
        'id': note.id,
        'user_id': note.user_id,
        'display_name': getattr(note.user, 'profile', None) and note.user.profile.display_name or note.user.username,
        'avatar': avatar_url,
        'text': note.text,
        'audio_id': note.audio_id,
        'audio_title': note.audio.title if note.audio else None,
        'audio_artist': note.audio.artist if note.audio else None,
        'audio_url': audio_url,
        'audio_start_sec': note.audio_start_sec,
        'expires_at': note.expires_at.isoformat() if note.expires_at else None,
        'created_at': note.created_at.isoformat(),
        'likes_count': note.likes.count() if hasattr(note, 'likes') else 0,
        'is_liked': note.likes.filter(user=request.user).exists() if hasattr(note, 'likes') else False,
        'mentions': list(note.mentions.values_list('id', flat=True)) if hasattr(note, 'mentions') else [],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_note(request):
    try:
        note = Note.objects.get(user=request.user)
        # Auto-expire check
        if note.expires_at and note.expires_at < timezone.now():
            note.delete()
            return Response({'note': None})
        return Response({'note': _note_data(note, request)})
    except Note.DoesNotExist:
        return Response({'note': None})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_note(request):
    """Create or update the current user's note."""
    text = request.data.get('text', '').strip()
    audio_id = request.data.get('audio_id')
    audio_start_sec = int(request.data.get('audio_start_sec', 0))
    expires_hours = int(request.data.get('expires_hours', 24))

    if not text and not audio_id:
        return Response({'error': 'text or audio_id required'}, status=400)

    expires_at = timezone.now() + timedelta(hours=expires_hours)
    audio_meta = request.data.get('audio_meta')
    audio = None
    
    if audio_id:
        try:
            audio = Audio.objects.get(pk=audio_id)
        except (Audio.DoesNotExist, ValueError):
            # It's an external string ID, we need to create it from audio_meta
            pass

    if not audio and audio_meta and isinstance(audio_meta, dict):
        try:
            title = audio_meta.get('title', 'Original Audio')
            artist = audio_meta.get('artist', 'Unknown')
            cover_url = audio_meta.get('coverArt', '')
            ext_url = audio_meta.get('url', '')
            
            audio, created = Audio.objects.get_or_create(
                title=title, artist=artist,
                defaults={'created_by': request.user, 'cover_image_url': cover_url}
            )
            
            if created and ext_url:
                audio.file_url = ext_url
                audio.save()
        except Exception as e:
            print(f"Error creating audio for note from meta: {e}")

    note, _ = Note.objects.update_or_create(
        user=request.user,
        defaults={
            'text': text,
            'audio': audio,
            'audio_start_sec': audio_start_sec,
            'expires_at': expires_at,
        }
    )
    
    # Handle mentions
    import re
    from django.contrib.auth.models import User
    mention_usernames = [m.strip('@') for m in re.findall(r'@\w+', text)]
    if mention_usernames:
        mentioned_users = User.objects.filter(username__in=mention_usernames)
        note.mentions.set(mentioned_users)
        
        # Notify mentioned users
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        from ..notifications.services import create_notification
        profile = getattr(request.user, 'profile', None)
        sender_name = profile.display_name if profile else request.user.username
        for u in mentioned_users:
            if u != request.user:
                create_notification(
                    recipient=u,
                    actor=request.user,
                    notification_type='note_mention',
                    message=f"{sender_name} mentioned you in their note.",
                    object_id=note.id
                )
                tokens = _get_user_tokens(u.id)
                if tokens:
                    send_push_notification(tokens, title="New Mention", body=f"{sender_name} mentioned you in their note.", data={'type': 'note_mention'})
    else:
        note.mentions.clear()

    return Response({'note': _note_data(note, request)})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_note(request):
    Note.objects.filter(user=request.user).delete()
    return Response({'ok': True})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_friend_notes(request):
    """List notes from people the current user follows."""
    from django.contrib.auth.models import User
    from ...models import Follow
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)

    notes = Note.objects.filter(
        user_id__in=list(following_ids)
    ).select_related('user', 'user__profile', 'audio').order_by('-created_at')

    # Filter expired
    now = timezone.now()
    active_notes = [n for n in notes if not n.expires_at or n.expires_at > now]

    return Response([_note_data(n, request) for n in active_notes])

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_note_view(request, pk: int):
    from ...models import NoteLike
    try:
        note = Note.objects.get(pk=pk)
    except Note.DoesNotExist:
        return Response({'error': 'Note not found'}, status=404)
        
    like, created = NoteLike.objects.get_or_create(note=note, user=request.user)
    if not created:
        like.delete()
        return Response({'liked': False, 'likes_count': note.likes.count()})
        
    # Send Notification
    if note.user != request.user:
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        from ..notifications.services import create_notification
        profile = getattr(request.user, 'profile', None)
        sender_name = profile.display_name if profile else request.user.username
        
        create_notification(
            recipient=note.user,
            actor=request.user,
            notification_type='note_like',
            message=f"{sender_name} liked your note.",
            object_id=note.id
        )
        tokens = _get_user_tokens(note.user.id)
        if tokens:
            send_push_notification(
                tokens, 
                title="Note Liked", 
                body=f"{sender_name} liked your note.", 
                data={'type': 'note_like'}
            )
            
    return Response({'liked': True, 'likes_count': note.likes.count()})

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from ...models import Note, Audio


def _note_data(note, request):
    from ...utils import get_absolute_media_url
    
    # Unified music metadata
    music_data = None
    if note.music_track:
        music_data = {
            'title': note.music_track.title,
            'artist': note.music_track.artist_name,
            'cover_art': note.music_track.cover_image_url,
            'url': note.music_track.preview_url,
            'provider': note.music_track.provider_name,
            'provider_track_id': note.music_track.provider_track_id,
            'duration': note.music_track.duration
        }
    elif note.audio:
        music_data = {
            'title': note.audio.title,
            'artist': note.audio.artist,
            'cover_art': get_absolute_media_url(note.audio.cover_image_url, request),
            'url': get_absolute_media_url(note.audio.file_url, request),
            'provider': 'legacy',
            'duration': note.audio.duration_ms / 1000 if note.audio.duration_ms else 0
        }

    avatar_url = None
    if hasattr(note.user, 'profile') and note.user.profile.photo:
        avatar_url = get_absolute_media_url(note.user.profile.photo, request)

    return {
        'id': note.id,
        'user_id': note.user_id,
        'display_name': getattr(note.user, 'profile', None) and note.user.profile.display_name or note.user.username,
        'avatar': avatar_url,
        'text': note.text,
        'music': music_data,
        'audio_start_sec': note.audio_start_sec,
        'editor_metadata': note.editor_metadata_json,
        'expires_at': note.expires_at.isoformat() if note.expires_at else None,
        'created_at': note.created_at.isoformat(),
        'likes_count': note.likes.count() if hasattr(note, 'likes') else 0,
        'is_liked': note.likes.filter(user=request.user).exists() if hasattr(note, 'likes') else False,
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_note(request):
    try:
        note = Note.objects.filter(user=request.user).select_related('music_track', 'audio').first()
        if not note:
            return Response({'note': None})
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
    """Create or update the current user's note with modern music support."""
    from api.services.music_service import MusicService
    
    text = request.data.get('text', '').strip()
    provider_track_id = request.data.get('provider_track_id')
    provider_name = request.data.get('provider_name', 'jiosaavn')
    audio_id = request.data.get('audio_id')
    audio_start_sec = float(request.data.get('audio_start_sec', 0))
    expires_hours = int(request.data.get('expires_hours', 24))
    editor_metadata = request.data.get('editor_metadata', {})

    expires_at = timezone.now() + timedelta(hours=expires_hours)
    
    music_track = None
    if provider_track_id:
        music_track = MusicService.get_track(provider_track_id, provider_name)

    audio = None
    if not music_track and audio_id:
        try:
            audio = Audio.objects.get(pk=audio_id)
        except:
            pass

    note, _ = Note.objects.update_or_create(
        user=request.user,
        defaults={
            'text': text,
            'music_track': music_track,
            'audio': audio,
            'audio_start_sec': audio_start_sec,
            'expires_at': expires_at,
            'editor_metadata_json': editor_metadata
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
def get_user_note(request, user_id: int):
    """Return the active note for a specific user (for viewing on their public profile)."""
    try:
        note = Note.objects.get(user_id=user_id)
        if note.expires_at and note.expires_at < timezone.now():
            note.delete()
            return Response({'note': None})
        return Response({'note': _note_data(note, request)})
    except Note.DoesNotExist:
        return Response({'note': None})


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

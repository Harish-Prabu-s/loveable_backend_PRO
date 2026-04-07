from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from ...models import Note, Audio


def _note_data(note, request):
    audio_url = None
    if note.audio and note.audio.file_url:
        audio_url = request.build_absolute_uri(note.audio.file_url.url)
    avatar_url = None
    if hasattr(note.user, 'profile') and note.user.profile.photo:
        avatar_url = request.build_absolute_uri(note.user.profile.photo.url)
    return {
        'id': note.id,
        'user_id': note.user_id,
        'display_name': getattr(note.user, 'profile', None) and note.user.profile.display_name or note.user.username,
        'avatar': avatar_url,
        'text': note.text,
        'audio_id': note.audio_id,
        'audio_title': note.audio.title if note.audio else None,
        'audio_url': audio_url,
        'audio_start_sec': note.audio_start_sec,
        'expires_at': note.expires_at.isoformat() if note.expires_at else None,
        'created_at': note.created_at.isoformat(),
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
    audio = None
    if audio_id:
        try:
            audio = Audio.objects.get(pk=audio_id)
        except Audio.DoesNotExist:
            pass

    note, _ = Note.objects.update_or_create(
        user=request.user,
        defaults={
            'text': text,
            'audio': audio,
            'audio_start_sec': audio_start_sec,
            'expires_at': expires_at,
        }
    )
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

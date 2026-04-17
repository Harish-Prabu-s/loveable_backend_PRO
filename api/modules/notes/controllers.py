from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from ...models import Note, Audio
from .serializers import (
    NoteSerializer, 
    CreateOrReplaceNoteSerializer, 
    MyNoteSerializer, 
    ChatRowNoteSerializer
)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_note(request):
    """Fetch the current user's active note."""
    note = Note.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).first()
    
    if not note:
        return Response({'note': None})
        
    serializer = MyNoteSerializer(note, context={'request': request})
    return Response({'note': serializer.data})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_or_replace_note(request):
    """Create a new note or replace the existing active one."""
    serializer = CreateOrReplaceNoteSerializer(data=request.data)
    if serializer.is_valid():
        # Deactivate old notes
        Note.objects.filter(
            user=request.user,
            is_active=True,
            expires_at__gt=timezone.now()
        ).update(is_active=False)
        
        # Create new note
        new_note = serializer.save(
            user=request.user,
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        return Response(NoteSerializer(new_note, context={'request': request}).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_my_note(request):
    """Mark current active note as inactive."""
    Note.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).update(is_active=False)
    return Response({'status': 'deleted'}, status=status.HTTP_204_NO_CONTENT)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_chat_row(request):
    """Fetch notes for the top chat row (my note first, then others)."""
    # My note
    my_note_obj = Note.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    ).first()
    my_note = ChatRowNoteSerializer(my_note_obj, context={'request': request}).data if my_note_obj else None
    
    # Others' notes (only friends/followed users if necessary, or all active notes for now as per simple social logic)
    # The requirement says "sort by recent note activity or recent interaction"
    # For now, let's get active notes from people I follow or all if follows are not strictly required for DM list
    from ...models import Follow
    following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    
    other_notes_objs = Note.objects.filter(
        user_id__in=following_ids,
        is_active=True,
        expires_at__gt=timezone.now()
    ).exclude(user=request.user).select_related('user', 'user__profile').order_by('-created_at')
    
    notes = ChatRowNoteSerializer(other_notes_objs, many=True, context={'request': request}).data
    
    return Response({
        'my_note': my_note,
        'notes': notes
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_note_detail(request, pk):
    """Fetch detail for a specific note."""
    try:
        note = Note.objects.get(pk=pk, is_active=True, expires_at__gt=timezone.now())
        serializer = NoteSerializer(note, context={'request': request})
        return Response(serializer.data)
    except Note.DoesNotExist:
        return Response({'detail': 'Note not found or expired'}, status=status.HTTP_404_NOT_FOUND)


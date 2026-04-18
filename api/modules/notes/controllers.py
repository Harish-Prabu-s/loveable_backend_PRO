from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q, Count, Exists, OuterRef
from ...models import Note, Audio, NoteLike, User
from .serializers import (
    NoteSerializer, 
    CreateOrReplaceNoteSerializer, 
    MyNoteSerializer, 
    ChatRowNoteSerializer
)

def annotate_note_queryset(queryset, user):
    """Helper to annotate note queryset with likes_count and is_liked."""
    if user.is_authenticated:
        is_liked = Exists(NoteLike.objects.filter(note=OuterRef('pk'), user=user))
    else:
        is_liked = None
    
    return queryset.annotate(
        likes_count=Count('likes'),
        is_liked=is_liked
    )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_my_note(request):
    """Fetch the current user's active note."""
    queryset = Note.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    )
    note = annotate_note_queryset(queryset, request.user).first()
    
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
        
        # Reload with annotations
        queryset = Note.objects.filter(pk=new_note.pk)
        annotated_note = annotate_note_queryset(queryset, request.user).first()
        
        return Response(NoteSerializer(annotated_note, context={'request': request}).data, status=status.HTTP_201_CREATED)
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
    my_note_queryset = Note.objects.filter(
        user=request.user,
        is_active=True,
        expires_at__gt=timezone.now()
    )
    my_note_obj = annotate_note_queryset(my_note_queryset, request.user).first()
    my_note = ChatRowNoteSerializer(my_note_obj, context={'request': request}).data if my_note_obj else None
    
    # Others' notes
    from ...models import Follow
    following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    
    # If following no one, maybe show everyone for discoverability or testing?
    # Actually, let's stick to following but ensure it works.
    
    other_notes_queryset = Note.objects.filter(
        user_id__in=following_ids,
        is_active=True,
        expires_at__gt=timezone.now()
    ).exclude(user=request.user).select_related('user', 'user__profile').order_by('-created_at')
    
    other_notes_objs = annotate_note_queryset(other_notes_queryset, request.user)
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
        queryset = Note.objects.filter(pk=pk, is_active=True, expires_at__gt=timezone.now())
        note = annotate_note_queryset(queryset, request.user).get()
        serializer = NoteSerializer(note, context={'request': request})
        return Response(serializer.data)
    except Note.DoesNotExist:
        return Response({'detail': 'Note not found or expired'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_like(request, pk):
    """Toggle like on a note."""
    try:
        note = Note.objects.get(pk=pk)
        like, created = NoteLike.objects.get_or_create(note=note, user=request.user)
        if not created:
            like.delete()
            liked = False
        else:
            liked = True
        
        likes_count = note.likes.count()
        return Response({'is_liked': liked, 'likes_count': likes_count})
    except Note.DoesNotExist:
        return Response({'detail': 'Note not found'}, status=status.HTTP_404_NOT_FOUND)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_note(request, user_id):
    """Fetch the active note for a specific user."""
    queryset = Note.objects.filter(
        user_id=user_id,
        is_active=True,
        expires_at__gt=timezone.now()
    )
    note = annotate_note_queryset(queryset, request.user).first()
    
    return Response({'note': NoteSerializer(note, context={'request': request}).data if note else None})


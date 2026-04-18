import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.models import Note, User
from api.modules.notes.controllers import annotate_note_queryset
from api.modules.notes.serializers import ChatRowNoteSerializer
from django.test import RequestFactory
from django.utils import timezone

def test_chat_row():
    user = User.objects.get(id=2)
    request = RequestFactory().get('/')
    request.user = user
    
    # My note logic from controller
    my_note_queryset = Note.objects.filter(
        user=user,
        is_active=True,
        expires_at__gt=timezone.now()
    )
    my_note_obj = annotate_note_queryset(my_note_queryset, user).first()
    my_note = ChatRowNoteSerializer(my_note_obj, context={'request': request}).data if my_note_obj else None
    
    print(f"User 2 My Note: {my_note}")
    
    # Others' notes
    from api.models import Follow
    following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    
    all_notes = Note.objects.filter(
        is_active=True,
        expires_at__gt=timezone.now()
    ).exclude(user=user)
    
    friend_notes = all_notes.filter(user_id__in=following_ids)
    if friend_notes.exists():
        other_notes_queryset = friend_notes
    else:
        other_notes_queryset = all_notes
            
    other_notes_queryset = other_notes_queryset.select_related('user', 'user__profile').order_by('-created_at')[:15]
    other_notes_objs = annotate_note_queryset(other_notes_queryset, user)
    notes = ChatRowNoteSerializer(other_notes_objs, many=True, context={'request': request}).data
    
    print(f"Others Notes Count: {len(notes)}")
    for n in notes:
        print(f" - Note {n['id']} by {n['username']} (display: {n['display_name']})")

if __name__ == "__main__":
    test_chat_row()

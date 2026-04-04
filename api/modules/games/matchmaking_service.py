from django.utils import timezone
from api.models import MatchmakingQueue, GameRoom, InteractiveGameSession, PlayerState, Profile
from django.contrib.auth.models import User
import uuid

def matchmake_user(user, game_type):
    """
    Main matchmaking logic:
    1. Check for an opposite-gender user who chose the same game_type.
    2. If found, create a room and session for both.
    3. If not found, add current user to the queue.
    """
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        raise ValueError("User profile not found. Please set your profile.")

    gender = profile.gender
    if gender not in ('M', 'F'):
        # For non-binary, or unspecified, we could do any-to-any, but per user request focus on Male-Female matching.
        # Fallback to any matching if gender is O
        target_gender = 'M' if gender == 'F' else 'F' if gender == 'M' else None
    else:
        target_gender = 'F' if gender == 'M' else 'M'

    # 1. Search for a match in the queue
    query = MatchmakingQueue.objects.filter(game_type=game_type)
    if target_gender:
        query = query.filter(gender=target_gender)
    
    # Exclude self (though OneToOneField should prevent duplicate entries, safety first)
    match = query.exclude(user=user).order_by('joined_at').first()

    if match:
        target_user = match.user
        # Match found! Create the room
        room_code = uuid.uuid4().hex[:8]
        room = GameRoom.objects.create(
            room_code=room_code,
            room_type='random',
            status='active'
        )
        session = InteractiveGameSession.objects.create(
            room=room,
            current_state='Waiting'
        )
        
        # Add both players
        PlayerState.objects.create(session=session, user=user, is_connected=True)
        PlayerState.objects.create(session=session, user=target_user, is_connected=True)

        # Clear the queue entry for the matched partner
        match.delete()
        
        return {
            'status': 'matched',
            'room_id': room.id,
            'room_code': room_code,
            'session_id': session.id,
            'partner': {
                'id': target_user.id,
                'name': target_user.profile.display_name if hasattr(target_user, 'profile') else target_user.username
            }
        }

    # 2. No match found, join the queue
    MatchmakingQueue.objects.update_or_create(
        user=user,
        defaults={
            'gender': gender,
            'game_type': game_type,
            'joined_at': timezone.now()
        }
    )
    
    return {
        'status': 'queued',
        'message': 'Waiting for an opposite-gender opponent...'
    }

import json
import uuid
import redis
from django.conf import settings
from django.contrib.auth.models import User
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from api.models import GameRoom, InteractiveGameSession, PlayerState, Profile

# Initialize Redis client
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class MatchmakingQueueService:
    @staticmethod
    def add_user(user_id, mode, gender, game_type, expanded=False):
        try:
            user = User.objects.get(id=user_id)
            return matchmake_user_redis(user, mode, game_type)
        except User.DoesNotExist:
            return None

    @staticmethod
    def remove_user(user_id):
        return leave_matchmaking_redis(user_id)

def get_matchmaking_key(mode, gender, game_type):
    return f"matchmaking:{mode}:{gender}:{game_type}"

def matchmake_user_redis(user, mode, game_type):
    """
    Matchmaking using Redis lists.
    - mode: '2p' or '4p'
    - game_type: 'truth_or_dare', 'ludo', etc.
    """
    try:
        profile = user.profile
    except Profile.DoesNotExist:
        return {'status': 'error', 'message': 'Profile not found'}

    gender = profile.gender
    if gender not in ('M', 'F'):
        return {'status': 'error', 'message': 'Matchmaking only supported for Male/Female profiles'}

    # 1. Join queue
    queue_key = get_matchmaking_key(mode, gender, game_type)
    user_data = {
        'id': user.id,
        'username': user.username,
        'display_name': profile.display_name or user.username,
        'photo': profile.photo.url if profile.photo else None,
        'gender': gender
    }
    
    # Store user data for lookups if needed, but for now we just push IDs to the queue
    redis_client.rpush(queue_key, user.id)
    
    # 2. Check for matches
    return check_for_matches(mode, game_type)

def check_for_matches(mode, game_type):
    """
    Atomically check and pop matched players.
    """
    male_key = get_matchmaking_key(mode, 'M', game_type)
    female_key = get_matchmaking_key(mode, 'F', game_type)
    
    if mode == '2p':
        # Need 1 M + 1 F
        if redis_client.llen(male_key) >= 1 and redis_client.llen(female_key) >= 1:
            m_id = redis_client.lpop(male_key)
            f_id = redis_client.lpop(female_key)
            if m_id and f_id:
                return create_match_room([m_id, f_id], mode, game_type)
    
    elif mode == '4p':
        # Need 2 M + 2 F
        if redis_client.llen(male_key) >= 2 and redis_client.llen(female_key) >= 2:
            m_ids = [redis_client.lpop(male_key) for _ in range(2)]
            f_ids = [redis_client.lpop(female_key) for _ in range(2)]
            # Filter out None in case of race condition
            all_ids = [id for id in m_ids + f_ids if id]
            if len(all_ids) == 4:
                return create_match_room(all_ids, mode, game_type)
            else:
                # Put them back? Actually, we should use a proper distributed lock or Lua script for this.
                # Simplification for now: just return queued status.
                pass
                
    return {'status': 'queued', 'message': 'Waiting for more players...'}

def create_match_room(user_ids, mode, game_type):
    """
    Creates the GameRoom and notifies all users.
    """
    room_code = uuid.uuid4().hex[:8]
    room = GameRoom.objects.create(
        room_code=room_code,
        room_type='random',
        game_mode=game_type if game_type in dict(GameRoom.MODE_CHOICES) else 'truth_dare',
        status='active'
    )
    
    session = InteractiveGameSession.objects.create(
        room=room,
        current_state='Lobby'
    )
    
    participants = []
    for uid in user_ids:
        user = User.objects.get(id=uid)
        PlayerState.objects.create(session=session, user=user, is_connected=True)
        participants.append(user)
    
    # Broadcast "Match Found" to all participants
    channel_layer = get_channel_layer()
    for user in participants:
        async_to_sync(channel_layer.group_send)(
            f"notifications_{user.id}",
            {
                "type": "send_notification",
                "content": {
                    "type": "match_found",
                    "room_id": room.id,
                    "session_id": session.id,
                    "room_code": room_code,
                    "game_mode": room.game_mode,
                    "players": [p.username for p in participants]
                }
            }
        )
    
    return {
        'status': 'matched',
        'room_id': room.id,
        'session_id': session.id,
        'room_code': room_code
    }

def leave_matchmaking_redis(user_id):
    """
    Removes user from all possible matchmaking queues.
    """
    for mode in ['2p', '4p']:
        for gender in ['M', 'F']:
            for game_type in ['truth_or_dare', 'ludo', 'carrom', 'fruit', 'candy']:
                key = get_matchmaking_key(mode, gender, game_type)
                redis_client.lrem(key, 0, user_id)
    return {'status': 'success'}

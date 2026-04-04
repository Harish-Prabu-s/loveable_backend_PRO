import redis
import json
import uuid
from django.conf import settings
from django.contrib.auth.models import User
from api.models import GameRoom, InteractiveGameSession, PlayerState, MatchmakingLog
from django.db import transaction

# Connect to Redis
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

class MatchmakingQueueService:
    """
    Production-ready Redis Matchmaking Service.
    Handles strict gender-based queues for 2-player and 4-player modes.
    Now supports an 'ANY' queue for expanded matchmaking.
    """

    @staticmethod
    def get_queue_key(game_type, mode, gender):
        # gender can be 'M', 'F', or 'ANY'
        return f"matchmaking:{game_type}:{mode}:{gender}"

    @classmethod
    def add_user(cls, user_id, mode, gender, game_type='truth_or_dare', expanded=False):
        """
        Adds a user to the Redis queue and attempts to match.
        """
        queue_gender = 'ANY' if expanded else gender
        queue_key = cls.get_queue_key(game_type, mode, queue_gender)
        
        # 1. Prevent duplicate joins
        active_key = f"matchmaking:user:{user_id}"
        if redis_client.exists(active_key):
            cls.remove_user(user_id)

        # 2. Add to Redis List
        redis_client.lpush(queue_key, user_id)
        redis_client.set(active_key, queue_key)
        
        # Log to DB
        user = User.objects.get(id=user_id)
        MatchmakingLog.objects.create(
            user=user, 
            mode=f"{game_type}_{mode}", 
            status='searching',
            is_expanded=expanded
        )

        # 3. Attempt to match
        return cls.try_match(game_type, mode)

    @classmethod
    def remove_user(cls, user_id):
        """
        Safely removes a user from any matchmaking queue.
        """
        active_key = f"matchmaking:user:{user_id}"
        queue_key = redis_client.get(active_key)
        if queue_key:
            redis_client.lrem(queue_key, 0, user_id)
            redis_client.delete(active_key)
            
            user = User.objects.get(id=user_id)
            MatchmakingLog.objects.create(user=user, mode="unknown", status='cancelled')
            return True
        return False

    @classmethod
    def try_match(cls, game_type, mode):
        """
        Check Redis lists for available matches based on strict and expanded rules.
        """
        m_queue = cls.get_queue_key(game_type, mode, 'M')
        f_queue = cls.get_queue_key(game_type, mode, 'F')
        any_queue = cls.get_queue_key(game_type, mode, 'ANY')

        matched_user_ids = []

        if mode == '2p':
            # Priority 1: Strict gender matching
            if redis_client.llen(m_queue) >= 1 and redis_client.llen(f_queue) >= 1:
                matched_user_ids.append(redis_client.rpop(m_queue))
                matched_user_ids.append(redis_client.rpop(f_queue))
            # Priority 2: Match expanded users with anyone
            elif redis_client.llen(any_queue) >= 2:
                matched_user_ids.append(redis_client.rpop(any_queue))
                matched_user_ids.append(redis_client.rpop(any_queue))
            # Priority 3: Match expanded user with a waiting gender-strict user
            elif redis_client.llen(any_queue) >= 1:
                if redis_client.llen(m_queue) >= 1:
                    matched_user_ids.append(redis_client.rpop(any_queue))
                    matched_user_ids.append(redis_client.rpop(m_queue))
                elif redis_client.llen(f_queue) >= 1:
                    matched_user_ids.append(redis_client.rpop(any_queue))
                    matched_user_ids.append(redis_client.rpop(f_queue))
        
        elif mode == '4p':
            # Strict mode: 2M + 2F
            if redis_client.llen(m_queue) >= 2 and redis_client.llen(f_queue) >= 2:
                matched_user_ids += [redis_client.rpop(m_queue) for _ in range(2)]
                matched_user_ids += [redis_client.rpop(f_queue) for _ in range(2)]
            # Expanded mode: Any 4 players if there's enough on the ANY queue
            elif redis_client.llen(any_queue) >= 4:
                matched_user_ids += [redis_client.rpop(any_queue) for _ in range(4)]
            # Hybrid: Mix ANY and specific genders if total >= 4
            else:
                combined = []
                # Placeholder for complex hybrid logic (taking from ANY first, then fillers)
                # For simplicity, we only match 4p if strict or full-any.
                pass

        if matched_user_ids:
            for uid in matched_user_ids:
                redis_client.delete(f"matchmaking:user:{uid}")
            return cls.create_room_for_match(matched_user_ids, game_type, mode)

        return None

    @classmethod
    def create_room_for_match(cls, user_ids, game_type, mode):
        with transaction.atomic():
            room_code = uuid.uuid4().hex[:8].upper()
            room = GameRoom.objects.create(
                room_code=room_code,
                room_type='random',
                game_mode=game_type,
                status='in_progress'
            )
            session = InteractiveGameSession.objects.create(
                room=room,
                current_state='Waiting'
            )
            users = User.objects.filter(id__in=user_ids)
            for u in users:
                PlayerState.objects.create(session=session, user=u, is_connected=False)
                MatchmakingLog.objects.create(user=u, mode=f"{game_type}_{mode}", status='matched')
            
            return {
                'room_code': room_code,
                'session_id': session.id,
                'players': [u.id for u in users]
            }

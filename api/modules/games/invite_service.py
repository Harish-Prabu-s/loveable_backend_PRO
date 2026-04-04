from django.utils import timezone
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from api.models import GameRoom, InteractiveGameSession, PlayerState, Notification
from django.contrib.auth.models import User
from ..notifications.services import create_notification

def send_game_invite(sender, target_user_id, game_mode):
    """
    Creates a pending GameRoom and notifies the target user.
    """
    try:
        target_user = User.objects.get(id=target_user_id)
        import uuid
        room_code = uuid.uuid4().hex[:8]
        
        # 1. Create Room in 'waiting_approval' status
        room = GameRoom.objects.create(
            host=sender,
            room_code=room_code,
            room_type='couple',
            game_mode=game_mode,
            status='waiting_approval'
        )
        
        # 2. Create Session
        session = InteractiveGameSession.objects.create(
            room=room,
            current_state='Waiting'
        )
        
        # 3. Add Players
        PlayerState.objects.create(session=session, user=sender, is_connected=True)
        PlayerState.objects.create(session=session, user=target_user, is_connected=False)
        
        # 4. Create Notification
        create_notification(
            recipient=target_user,
            actor=sender,
            notification_type='game_invite',
            message=f"{sender.profile.display_name or sender.username} invited you to play {game_mode.replace('_', ' ').title()}",
            object_id=room.id
        )
        
        return {
            'status': 'success',
            'room_id': room.id,
            'room_code': room_code
        }
    except User.DoesNotExist:
        return {'status': 'error', 'message': 'User not found'}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def respond_game_invite(notification_id, user, action):
    """
    Accepts or Rejects a game invite.
    """
    try:
        notification = Notification.objects.get(id=notification_id, recipient=user)
        room = GameRoom.objects.get(id=notification.object_id)
        
        if action == 'accept':
            room.status = 'lobby'
            room.save()
            
            # Transition session
            session = room.game_sessions.first()
            if session:
                session.current_state = 'Lobby'
                session.save()
            
            # Update Notification
            notification.is_read = True
            # We can't easily change the type here without confusing the UI, 
            # so we use a status field if available.
            
            # Broadcast to Host that game is starting
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f"notifications_{room.host_id}",
                {
                    "type": "send_notification",
                    "content": {
                        "type": "game_invite_accepted",
                        "room_id": room.id,
                        "session_id": session.id if session else None,
                        "room_code": room.room_code,
                        "game_mode": room.game_mode,
                        "message": f"{user.username} joined the game!"
                    }
                }
            )
            
            return {
                'status': 'success',
                'room_id': room.id,
                'session_id': session.id if session else None,
                'room_code': room.room_code
            }
        else:
            room.status = 'rejected'
            room.save()
            notification.is_read = True
            notification.save()
            return {'status': 'success', 'message': 'Invite declined'}
            
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

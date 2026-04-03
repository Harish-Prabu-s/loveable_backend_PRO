from typing import Optional
from django.contrib.auth.models import User
from django.db.models import F
from django.db import models
from django.utils import timezone
from datetime import timedelta
from ...models import Room, Message, Streak

def get_or_create_room(caller: User, receiver_id: int, call_type: str) -> Room:
    receiver = User.objects.get(id=receiver_id)
    
    # Try finding an active/pending room in EITHER direction
    room = Room.objects.filter(
        (models.Q(caller=caller, receiver=receiver) | models.Q(caller=receiver, receiver=caller)),
        call_type=call_type,
        status__in=['pending', 'active']
    ).first()
    
    if not room:
        # Fallback to the latest room created between them
        room = Room.objects.filter(
            (models.Q(caller=caller, receiver=receiver) | models.Q(caller=receiver, receiver=caller)),
            call_type=call_type
        ).order_by('-created_at').first()

    if not room:
        room = Room.objects.create(caller=caller, receiver=receiver, call_type=call_type, status='pending')
        
        # Trigger FCM notification for new calls
        if call_type in ['audio', 'video']:
            try:
                from ..notifications.fcm_service import send_call_notification
                profile = getattr(caller, 'profile', None)
                caller_name = profile.display_name if profile else caller.username
                send_call_notification(caller_name, receiver.id, room.id, call_type)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Failed to send call FCM: {e}")
                
    return room

def list_my_rooms(user: User):
    return Room.objects.filter(is_archived=False).filter(models.Q(caller=user) | models.Q(receiver=user)).order_by('-created_at')

def list_messages(room_id: int):
    room = Room.objects.get(id=room_id)
    now = timezone.now()

    # Expire messages that have passed expires_at
    Message.objects.filter(room_id=room_id, expires_at__lt=now).delete()

    return Message.objects.filter(room_id=room_id).order_by('created_at')

def mark_messages_seen(room_id: int, user: User):
    try:
        room = Room.objects.get(id=room_id)
        # Identify the recipient of the seen notification
        other_user = room.receiver if room.caller == user else room.caller
        
        unseen_msgs = Message.objects.filter(room_id=room_id, is_seen=False).exclude(sender=user)
        
        if room.disappearing_messages_enabled and room.disappearing_timer > 0:
            expiry_time = timezone.now() + timedelta(seconds=room.disappearing_timer)
            unseen_msgs.update(is_seen=True, expires_at=expiry_time)
        else:
            unseen_msgs.update(is_seen=True)
            
        # Notify sender that their messages were read
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'chat_{other_user.id}',
                {
                    'type': 'send_message',
                    'content': {
                        'type': 'messages_seen',
                        'room_id': room.id
                    }
                }
            )
    except Room.DoesNotExist:
        pass
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error marking messages seen: {e}")

def send_message(
    room_id: int,
    sender: User,
    content: str,
    msg_type: str = 'text',
    media_url: Optional[str] = None,
    duration_seconds: int = 0,
) -> Message:
    room = Room.objects.get(id=room_id)
    other_user = room.receiver if room.caller == sender else room.caller

    # Update Streak logic
    update_streak(sender, other_user)

    # Coin Deduction Logic
    from ..monetization.services import get_chat_cost, get_media_cost
    from ...models import Wallet, CoinTransaction
    from django.db import transaction

    cost = 0
    if msg_type == 'text':
        cost = get_chat_cost()
    elif msg_type == 'image':
        cost = get_media_cost('photo')
    elif msg_type == 'video':
        cost = get_media_cost('video_msg')
    elif msg_type == 'voice':
        cost = get_media_cost('voice_msg')

    if cost > 0:
        wallet, _ = Wallet.objects.get_or_create(user=sender)
        if wallet.coin_balance < cost:
            raise Exception("Insufficient coins")
        
        with transaction.atomic():
            wallet.coin_balance = models.F('coin_balance') - cost
            wallet.total_spent = models.F('total_spent') + cost
            wallet.save(update_fields=['coin_balance', 'total_spent'])
            
            CoinTransaction.objects.create(
                wallet=wallet,
                type='debit',
                transaction_type='chat_spent',
                amount=cost,
                description=f'Sent {msg_type} message'
            )

    msg = Message.objects.create(
        room_id=room_id,
        sender=sender,
        content=content,
        type=msg_type,
        media_url=media_url,
        duration_seconds=duration_seconds,
    )
    
    # Notify Receiver in Real-Time (Chat Channel)
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from ...serializers import MessageSerializer
    channel_layer = get_channel_layer()
    if channel_layer:
        async_to_sync(channel_layer.group_send)(
            f'chat_{other_user.id}',
            {
                'type': 'send_message',
                'content': {
                    'type': 'new_message',
                    'message': MessageSerializer(msg).data
                }
            }
        )
    
    # Push Notification
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    tokens = _get_user_tokens(other_user.id)
    if tokens:
        profile = getattr(sender, 'profile', None)
        sender_name = profile.display_name if profile else sender.username
        send_push_notification(
            tokens, 
            title=f"New message from {sender_name}", 
            body=content[:50] + ("..." if len(content) > 50 else ""),
            data={'type': 'chat_message', 'sender_id': sender.id}
        )
        
    return msg

def update_streak(sender: User, receiver: User):
    """
    Optimized streak logic with error handling and last_uploader tracking.
    """
    try:
        # Ensure consistent ordering for unique constraint
        u1, u2 = (sender, receiver) if sender.id < receiver.id else (receiver, sender)
        
        streak, created = Streak.objects.get_or_create(user1=u1, user2=u2)
        now = timezone.now()
        
        # Track who last sent a message to progress the streak
        streak.last_uploader = sender
        
        if created or not streak.last_interaction_date:
            streak.streak_count = 1
            streak.last_interaction_date = now
        else:
            delta = now - streak.last_interaction_date
            
            # If same day, don't increment but update uploader
            if delta.days == 0 and now.date() == streak.last_interaction_date.date():
                pass 
            # If exactly next day, increment
            elif delta.days == 1 or (delta.days == 0 and now.date() > streak.last_interaction_date.date()):
                streak.streak_count += 1
                streak.last_interaction_date = now
            else:
                # Streak lost, check freezes
                if streak.freezes_available > 0:
                    streak.freezes_available -= 1
                    streak.last_interaction_date = now # Use freeze to save streak
                else:
                    streak.streak_count = 1 # Reset
                    streak.last_interaction_date = now
        
        streak.save()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Failed to update streak: {e}")

def mark_room_status(room_id: int, status: str, duration_seconds: int = 0, coins_spent: int = 0):
    room = Room.objects.filter(id=room_id).first()
    if not room:
        return None
    room.status = status
    if status == 'active' and not room.started_at:
        room.started_at = timezone.now()
    if status == 'ended':
        room.ended_at = timezone.now()
        if duration_seconds:
            room.duration_seconds = duration_seconds
        if coins_spent:
            room.coins_spent = coins_spent
    room.save()
    return room

def presence_status(user_id: int) -> str:
    active = Room.objects.filter(receiver_id=user_id, status='active').exists() or Room.objects.filter(caller_id=user_id, status='active').exists()
    return 'busy' if active else 'active'

def archive_room(room_id: int, user: User):
    """Archive a chat room."""
    try:
        room = Room.objects.get(id=room_id)
        if room.caller != user and room.receiver != user:
            return False
        room.is_archived = True
        room.save(update_fields=['is_archived'])
        return True
    except Room.DoesNotExist:
        return False

def unarchive_room(room_id: int, user: User):
    """Unarchive a chat room."""
    try:
        room = Room.objects.get(id=room_id)
        if room.caller != user and room.receiver != user:
            return False
        room.is_archived = False
        room.save(update_fields=['is_archived'])
        return True
    except Room.DoesNotExist:
        return False

def update_room_theme(room_id: int, chat_theme: str):
    """Update the chat theme and notify participants."""
    try:
        room = Room.objects.get(id=room_id)
        room.chat_theme = chat_theme
        room.save(update_fields=['chat_theme'])
        
        # Notify Participants in Real-Time
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            # Notify both participants
            participants = [room.caller.id, room.receiver.id]
            for user_id in participants:
                async_to_sync(channel_layer.group_send)(
                    f'chat_{user_id}',
                    {
                        'type': 'send_message',
                        'content': {
                            'type': 'theme_updated',
                            'room_id': room.id,
                            'theme_id': chat_theme
                        }
                    }
                )
        return True
    except Room.DoesNotExist:
        return False
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error updating room theme: {e}")
        return False

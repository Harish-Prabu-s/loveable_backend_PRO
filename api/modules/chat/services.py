from typing import Optional
from django.contrib.auth.models import User
from django.db.models import F
from django.db import models
from django.utils import timezone
from datetime import timedelta
from ...models import Room, Message, Streak, RoomMember, MessageSeen, MessageReaction

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

def create_group_room(creator: User, name: str, member_ids: list[int], avatar: Optional[str] = None) -> Room:
    """Create a new group room and add the specified members."""
    room = Room.objects.create(
        caller=creator,
        is_group=True,
        name=name,
        group_avatar=avatar,
        status='pending'
    )
    
    # Add creator as admin
    RoomMember.objects.create(room=room, user=creator, role='admin')
    
    # Add other members
    for m_id in member_ids:
        if m_id != creator.id:
            try:
                user = User.objects.get(id=m_id)
                RoomMember.objects.create(room=room, user=user, role='member')
                # Optional: Send push notification about group invite
            except User.DoesNotExist:
                continue
                
    return room

def add_group_member(room_id: int, user_id: int) -> bool:
    """Add a new member to an existing group room."""
    try:
        room = Room.objects.get(id=room_id, is_group=True)
        user = User.objects.get(id=user_id)
        RoomMember.objects.get_or_create(room=room, user=user)
        return True
    except (Room.DoesNotExist, User.DoesNotExist):
        return False

def list_my_rooms(user: User):
    # Get private rooms where user is caller or receiver
    private_rooms = Room.objects.filter(is_archived=False, is_group=False).filter(models.Q(caller=user) | models.Q(receiver=user))
    # Get group rooms where user is a member
    group_rooms = Room.objects.filter(is_archived=False, is_group=True, members__user=user)
    
    return (private_rooms | group_rooms).distinct().order_by('-created_at')

def list_messages(room_id: int):
    room = Room.objects.get(id=room_id)
    now = timezone.now()

    # Expire messages that have passed expires_at
    Message.objects.filter(room_id=room_id, expires_at__lt=now).delete()

    return Message.objects.filter(room_id=room_id).order_by('created_at')

def mark_messages_seen(room_id: int, user: User):
    try:
        room = Room.objects.get(id=room_id)
        unseen_msgs = Message.objects.filter(room_id=room_id, is_seen=False).exclude(sender=user)
        
        # Mark as seen in per-user tracking
        msgs_to_update = []
        for msg in unseen_msgs:
            MessageSeen.objects.get_or_create(message=msg, user=user)
            msgs_to_update.append(msg)
            
        # For 1v1, also update is_seen boolean and seen_at
        if not room.is_group:
            now = timezone.now()
            if room.disappearing_messages_enabled and room.disappearing_timer > 0:
                expiry_time = now + timedelta(seconds=room.disappearing_timer)
                unseen_msgs.update(is_seen=True, seen_at=now, expires_at=expiry_time)
            else:
                unseen_msgs.update(is_seen=True, seen_at=now)
        
        # Notify Participants in Real-Time
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            # Group specific: broadcast who saw what
            targets = []
            if room.is_group:
                targets = [m.user_id for m in room.members.all()]
            else:
                other_user = room.receiver if room.caller == user else room.caller
                targets = [other_user.id]

            for u_id in targets:
                if u_id != user.id:
                    async_to_sync(channel_layer.group_send)(
                        f'chat_{u_id}',
                        {
                            'type': 'send_message',
                            'content': {
                                'type': 'messages_seen',
                                'room_id': room.id,
                                'user_id': user.id, # Who saw it
                                'messages': [m.id for m in msgs_to_update]
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
    reply_to_id: Optional[int] = None,
) -> Message:
    room = Room.objects.get(id=room_id)
    
    # Update Streak logic (Private chats only)
    if not room.is_group:
        other_user = room.receiver if room.caller == sender else room.caller
        if other_user:
            update_streak(sender, other_user)
    
    # Optional reply handling
    reply_to = None
    if reply_to_id:
        reply_to = Message.objects.filter(id=reply_to_id).first()

    # Coin Deduction/Reward Logic
    from ..monetization.services import get_chat_cost
    from ...models import Wallet, CoinTransaction
    from django.db import transaction

    # 1. Deduct for text (if applicable)
    if msg_type == 'text':
        cost = get_chat_cost()
        if cost > 0:
            wallet, _ = Wallet.objects.get_or_create(user=sender)
            if wallet.coin_balance < cost:
                raise Exception("Insufficient coins")
            other_user = room.receiver if room.caller == sender else room.caller
            target_name = getattr(other_user, 'profile', other_user).display_name if hasattr(other_user, 'profile') else other_user.username
            with transaction.atomic():
                wallet.coin_balance = models.F('coin_balance') - cost
                wallet.total_spent = models.F('total_spent') + cost
                wallet.save(update_fields=['coin_balance', 'total_spent'])
                CoinTransaction.objects.create(
                    wallet=wallet, amount=cost,
                    type='debit', transaction_type='chat_spent',
                    description=f"Sent text message to {target_name}",
                    target_user=other_user
                )

    # 2. Award for media (as per user request: Image=5, Video=10)
    elif msg_type in ['image', 'video']:
        reward = 5 if msg_type == 'image' else 10
        wallet, _ = Wallet.objects.get_or_create(user=sender)
        with transaction.atomic():
            wallet.coin_balance = models.F('coin_balance') + reward
            wallet.total_earned = models.F('total_earned') + reward
            wallet.save(update_fields=['coin_balance', 'total_earned'])
            CoinTransaction.objects.create(
                wallet=wallet, amount=reward,
                type='credit', transaction_type='earned',
                description=f'Reward for sharing {msg_type} in chat'
            )

    msg = Message.objects.create(
        room_id=room_id,
        sender=sender,
        content=content,
        type=msg_type,
        media_url=media_url,
        duration_seconds=duration_seconds,
        reply_to=reply_to
    )
    
    # Notify Participants in Real-Time (Chat Channel)
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    from ...serializers import MessageSerializer
    channel_layer = get_channel_layer()
    if channel_layer:
        targets = []
        if room.is_group:
            targets = [m.user_id for m in room.members.all()]
        else:
            other_user = room.receiver if room.caller == sender else room.caller
            targets = [other_user.id]

        for u_id in targets:
            if u_id != sender.id:
                async_to_sync(channel_layer.group_send)(
                    f'chat_{u_id}',
                    {
                        'type': 'send_message',
                        'content': {
                            'type': 'new_message',
                            'message': MessageSerializer(msg).data
                        }
                    }
                )
    
    # Push Notification for Recipients
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    
    recipients = []
    if room.is_group:
        recipients = [m.user for m in room.members.all().exclude(user=sender)]
    else:
        recipients = [room.receiver if room.caller == sender else room.caller]

    for recipient in recipients:
        tokens = _get_user_tokens(recipient.id)
        if tokens:
            profile = getattr(sender, 'profile', None)
            sender_name = profile.display_name if profile else sender.username
            title = f"{sender_name} in {room.name}" if room.is_group else f"New message from {sender_name}"
            send_push_notification(
                tokens, 
                title=title, 
                body=content[:50] + ("..." if len(content) > 50 else ""),
                data={'type': 'chat_message', 'sender_id': sender.id, 'room_id': room.id}
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

def expire_user_streaks(user: User):
    """
    Check and reset streaks that haven't been updated in 24+ hours.
    Can be called just-in-time when loading contact list.
    """
    from datetime import timedelta
    from django.utils import timezone
    from ...models import Streak
    
    threshold = timezone.now() - timedelta(hours=24)
    
    # Get all active streaks involving this user that are past the threshold
    streaks = Streak.objects.filter(
        models.Q(user1=user) | models.Q(user2=user),
        last_interaction_date__lt=threshold,
        streak_count__gt=0
    )
    
    for s in streaks:
        # Check if freeze can save it
        if s.freezes_available > 0:
            s.freezes_available -= 1
            # Push last interaction forward by 24h to "use" the freeze
            s.last_interaction_date = s.last_interaction_date + timedelta(hours=24)
            s.save()
        else:
            s.streak_count = 0
            s.last_uploader = None
            s.save()

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
            # Get all participants
            targets = []
            if room.is_group:
                targets = [m.user_id for m in room.members.all()]
            else:
                targets = [room.caller_id, room.receiver_id]

            for u_id in targets:
                async_to_sync(channel_layer.group_send)(
                    f'chat_{u_id}',
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
        import traceback
        import logging
        logging.getLogger(__name__).error(f"Error updating room theme: {e}\n{traceback.format_exc()}")
        return False

def react_message(message_id: int, user: User, emoji: str):
    """Add/Remove a reaction to a message and notify participants."""
    from ...models import Message, MessageReaction
    try:
        msg = Message.objects.get(id=message_id)
        room = msg.room
        
        # Toggle logic: if user already reacted with SAME emoji, remove it.
        # If they reacted with DIFFERENT emoji, we can either add another OR replace.
        # Common pattern: one reaction per user per message (replacing if different).
        # But unique_together says (message, user, emoji). Let's stick to toggle.
        
        existing = MessageReaction.objects.filter(message=msg, user=user, emoji=emoji).first()
        if existing:
            existing.delete()
            action = 'removed'
        else:
            MessageReaction.objects.create(message=msg, user=user, emoji=emoji)
            action = 'added'
            
        # Get all reactions for this message to broadcast
        all_reactions = list(MessageReaction.objects.filter(message=msg).values('user_id', 'emoji'))
        
        # Notify Participants in Real-Time
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            targets = []
            if room.is_group:
                targets = [m.user_id for m in room.members.all()]
            else:
                targets = [room.caller_id, room.receiver_id]

            for u_id in targets:
                async_to_sync(channel_layer.group_send)(
                    f'chat_{u_id}',
                    {
                        'type': 'send_message',
                        'content': {
                            'type': 'reaction_updated',
                            'message_id': message_id,
                            'room_id': room.id,
                            'user_id': user.id,
                            'emoji': emoji,
                            'action': action,
                            'all_reactions': all_reactions
                        }
                    }
                )
        return all_reactions
    except Message.DoesNotExist:
        raise Exception("Message not found")

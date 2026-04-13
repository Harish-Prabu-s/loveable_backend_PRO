from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...serializers import RoomSerializer, MessageSerializer, ContactSerializer, StreakSerializer
from .services import (
    get_or_create_room, list_my_rooms, list_messages, send_message, 
    presence_status, mark_room_status, mark_messages_seen, update_room_theme,
    create_group_room, add_group_member, expire_user_streaks
)
from django.db.models import Q, Max
from django.contrib.auth.models import User

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room_view(request):
    try:
        receiver_id = request.data.get('receiver_id')
        call_type = request.data.get('call_type', 'audio')
        if not receiver_id:
            return Response({'error': 'receiver_id required'}, status=400)
        room = get_or_create_room(request.user, int(receiver_id), call_type)
        return Response(RoomSerializer(room, context={'request': request}).data, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_detail_view(request, room_id: int):
    try:
        from ...models import Room
        # Just-in-time streak expiration check
        expire_user_streaks(request.user)
        
        # Allow if user is caller, receiver or a group member
        room = Room.objects.get(id=room_id)
        is_member = room.caller == request.user or room.receiver == request.user
        if not is_member and room.is_group:
            is_member = room.members.filter(user=request.user).exists()
            
        if not is_member:
            return Response({'error': 'forbidden'}, status=403)
            
        return Response(RoomSerializer(room, context={'request': request}).data)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_rooms_view(request):
    qs = list_my_rooms(request.user)
    return Response(RoomSerializer(qs, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messages_view(request, room_id: int):
    try:
        limit = int(request.GET.get('limit', 30))
        before_id = request.GET.get('before_id')   # cursor: load older messages
        before_id = int(before_id) if before_id else None

        qs = list_messages(room_id, limit=limit, before_id=before_id)
        serializer = MessageSerializer(qs, many=True, context={'request': request})
        return Response({
            'results': serializer.data,
            'has_more': len(qs) >= limit,   # if we got a full page, likely more exist
        })
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f'messages_view error: {e}')
        return Response({'results': [], 'has_more': False})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_seen_view(request, room_id: int):
    mark_messages_seen(room_id, request.user)
    return Response({'status': 'ok'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def toggle_disappearing_view(request, room_id: int):
    try:
        from ...models import Room
        room = Room.objects.get(id=room_id)
        if room.caller != request.user and room.receiver != request.user:
            return Response({'error': 'forbidden'}, status=403)
        
        enabled = request.data.get('enabled', False)
        timer = int(request.data.get('timer', 0))
        
        room.disappearing_messages_enabled = enabled
        room.disappearing_timer = timer
        room.save()
        
        return Response(RoomSerializer(room, context={'request': request}).data)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message_view(request, room_id: int):
    try:
        content = request.data.get('content')
        msg_type = request.data.get('type', 'text')
        media_url = request.data.get('media_url')
        duration_seconds = int(request.data.get('duration_seconds', 0))
        reply_to_id = request.data.get('reply_to_id')
        
        if not content and not media_url:
            return Response({'error': 'content or media required'}, status=400)
            
        msg = send_message(room_id, request.user, content or '', msg_type, media_url, duration_seconds, reply_to_id)
        return Response(MessageSerializer(msg, context={'request': request}).data, status=201)
    except Exception as e:
        if str(e) == "Insufficient coins":
            return Response({'error': 'Insufficient coins'}, status=402)
        import logging
        logging.getLogger(__name__).exception("Error sending message")
        return Response({'error': 'Failed to send message'}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_call_view(request, room_id: int):
    room = mark_room_status(room_id, 'active')
    if not room:
        return Response({'error': 'not_found'}, status=404)
    if room.caller != request.user and room.receiver != request.user:
        return Response({'error': 'forbidden'}, status=403)
    return Response(RoomSerializer(room, context={'request': request}).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def end_call_view(request, room_id: int):
    duration_seconds = int(request.data.get('duration_seconds', 0))
    coins_spent = int(request.data.get('coins_spent', 0))
    room = mark_room_status(room_id, 'ended', duration_seconds, coins_spent)
    if not room:
        return Response({'error': 'not_found'}, status=404)
    if room.caller != request.user and room.receiver != request.user:
        return Response({'error': 'forbidden'}, status=403)
    return Response(RoomSerializer(room, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def presence_view(request, user_id: int):
    status = presence_status(user_id)
    return Response({'status': status})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_list_view(request):
    try:    # Just-in-time streak expiration check
        expire_user_streaks(request.user)
        
        user = request.user
        from django.db.models import Prefetch, Count, Max
        from ...models import Room, Message, Streak
        
        # 1. Fetch 1v1 Rooms
        private_rooms = Room.objects.filter(is_group=False, is_archived=False) \
            .filter(Q(caller=user) | Q(receiver=user)) \
            .annotate(
                unread_count=Count('messages', filter=Q(messages__is_seen=False) & ~Q(messages__sender=user)),
                last_msg_time=Max('messages__created_at')
            ) \
            .filter(last_msg_time__isnull=False) \
            .select_related('caller__profile', 'receiver__profile') \
            .prefetch_related(Prefetch('messages', queryset=Message.objects.order_by('-created_at'), to_attr='latest_msgs'))

        # 2. Fetch Group Rooms
        group_rooms = Room.objects.filter(is_group=True, is_archived=False, members__user=user) \
            .annotate(
                unread_count=Count('messages', filter=~Q(messages__sender=user) & ~Q(messages__seen_by_users__user=user)),
                last_msg_time=Max('messages__created_at')
            ) \
            .prefetch_related(Prefetch('messages', queryset=Message.objects.order_by('-created_at'), to_attr='latest_msgs'))

        # Combine and Process
        contacts_data = []
        seen_user_ids = set()

        # Handle Private Rooms (map to User objects)
        for room in private_rooms:
            other_user = room.receiver if room.caller == user else room.caller
            if other_user.id in seen_user_ids: continue
            seen_user_ids.add(other_user.id)
            
            last_msg = room.latest_msgs[0] if room.latest_msgs else None
            if not last_msg: continue
            
            # Use dot notation for serializer compatibility
            other_user.is_group = False
            other_user.room_id = room.id
            other_user.user_id = other_user.id
            other_user.contact_id = room.id # Use room.id as the unique ID for the list
            other_user.last_message = last_msg.content
            other_user.last_message_type = last_msg.type
            other_user.last_timestamp = last_msg.created_at
            other_user.unread_count = room.unread_count
            
            # Streak (Simplified for performance)
            ot_id = other_user.id
            u1, u2 = (user.id, ot_id) if user.id < ot_id else (ot_id, user.id)
            streak = Streak.objects.filter(user1_id=u1, user2_id=u2).first()
            other_user.streak_count = streak.streak_count if streak else 0
            
            contacts_data.append(other_user)

        from types import SimpleNamespace
        for room in group_rooms:
            last_msg = room.latest_msgs[0] if room.latest_msgs else None
            
            # Dynamically set group avatar to last sender's avatar if available
            dynamic_avatar = room.group_avatar
            if last_msg and last_msg.sender_id:
                try:
                    from ...models import UserProfile
                    sender_prof = UserProfile.objects.get(user_id=last_msg.sender_id)
                    if sender_prof.photo:
                        dynamic_avatar = sender_prof.photo.url
                except Exception:
                    pass

            group_contact = SimpleNamespace(
                id=room.id,
                username=f"group_{room.id}",
                is_group=True,
                room_id=room.id,
                name=room.name,
                group_avatar=dynamic_avatar,
                last_message=last_msg.content if last_msg else "Start chatting...",
                last_message_type=last_msg.type if last_msg else "text",
                last_timestamp=last_msg.created_at if last_msg else room.created_at,
                unread_count=room.unread_count,
                streak_count=0
            )
            contacts_data.append(group_contact)

        # Final Sort by Last Timestamp
        contacts_data.sort(key=lambda x: x.last_timestamp if x.last_timestamp else timezone.now(), reverse=True)
            
        # Ensure 'id' is set to room.id for all entries to prevent duplicate keys in frontend
        for c in contacts_data:
            if hasattr(c, 'contact_id'):
                c.id = c.contact_id
                
        return Response(ContactSerializer(contacts_data, many=True, context={'request': request}).data)
    except Exception as e:
        import traceback
        import logging
        logging.getLogger(__name__).error(f"Error in contact_list_view: {e}\n{traceback.format_exc()}")
        return Response([])


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_theme_view(request, room_id: int):
    chat_theme = request.data.get('chat_theme')
    if not chat_theme:
        return Response({'error': 'chat_theme required'}, status=400)
    
    success = update_room_theme(room_id, chat_theme)
    if success:
        return Response({'status': 'ok'})
    return Response({'error': 'Failed to update theme or Room not found'}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def streak_leaderboard_view(request):
    # This was moved to streaks module
    return Response({'error': 'Moved to /api/streaks/leaderboard/'}, status=308)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group_view(request):
    try:
        name = request.data.get('name')
        user_ids = request.data.get('user_ids', [])
        avatar = request.data.get('group_avatar')
        
        if not name:
            return Response({'error': 'Group name required'}, status=400)
            
        room = create_group_room(request.user, name, user_ids, avatar)
        return Response(RoomSerializer(room, context={'request': request}).data, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_member_view(request, room_id: int):
    try:
        user_id = request.data.get('user_id')
        if not user_id:
            return Response({'error': 'user_id required'}, status=400)
            
        success = add_group_member(room_id, int(user_id))
        if success:
            return Response({'status': 'member added'})
        return Response({'error': 'Failed to add member'}, status=400)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def react_message_view(request, message_id: int):
    try:
        from .services import react_message
        emoji = request.data.get('emoji')
        if not emoji:
            return Response({'error': 'emoji required'}, status=400)
            
        reactions = react_message(message_id, request.user, emoji)
        return Response({'status': 'ok', 'reactions': reactions})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error reacting to message: {e}")
        return Response({'error': str(e)}, status=400)

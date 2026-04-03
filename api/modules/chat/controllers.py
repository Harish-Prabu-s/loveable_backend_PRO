from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...serializers import RoomSerializer, MessageSerializer, ContactSerializer, StreakSerializer
from .services import (
    get_or_create_room, list_my_rooms, list_messages, send_message, 
    presence_status, mark_room_status, mark_messages_seen, update_room_theme,
    create_group_room, add_group_member
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
        return Response(RoomSerializer(room).data, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_detail_view(request, room_id: int):
    try:
        from ...models import Room
        # Allow if user is caller, receiver or a group member
        room = Room.objects.get(id=room_id)
        is_member = room.caller == request.user or room.receiver == request.user
        if not is_member and room.is_group:
            is_member = room.members.filter(user=request.user).exists()
            
        if not is_member:
            return Response({'error': 'forbidden'}, status=403)
            
        return Response(RoomSerializer(room).data)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_detail_view(request, room_id: int):
    try:
        from ...models import Room
        # Allow if user is caller, receiver or a group member
        room = Room.objects.get(id=room_id)
        is_member = room.caller == request.user or room.receiver == request.user
        if not is_member and room.is_group:
            is_member = room.members.filter(user=request.user).exists()
            
        if not is_member:
            return Response({'error': 'forbidden'}, status=403)
            
        return Response(RoomSerializer(room).data)
    except Room.DoesNotExist:
        return Response({'error': 'Room not found'}, status=404)
    except Exception as e:
        return Response({'error': str(e)}, status=400)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_rooms_view(request):
    qs = list_my_rooms(request.user)
    return Response(RoomSerializer(qs, many=True).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def messages_view(request, room_id: int):
    qs = list_messages(room_id)
    return Response(MessageSerializer(qs, many=True).data)

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
        
        return Response(RoomSerializer(room).data)
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
        
        if not content and not media_url:
            return Response({'error': 'content or media required'}, status=400)
            
        msg = send_message(room_id, request.user, content or '', msg_type, media_url, duration_seconds)
        return Response(MessageSerializer(msg).data, status=201)
    except Exception as e:
        if str(e) == "Insufficient coins":
            return Response({'error': 'Insufficient coins'}, status=402)
        import logging
        logging.getLogger(__name__).error(f"Error sending message: {e}")
        return Response({'error': 'Failed to send message'}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_call_view(request, room_id: int):
    room = mark_room_status(room_id, 'active')
    if not room:
        return Response({'error': 'not_found'}, status=404)
    if room.caller != request.user and room.receiver != request.user:
        return Response({'error': 'forbidden'}, status=403)
    return Response(RoomSerializer(room).data)

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
    return Response(RoomSerializer(room).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def presence_view(request, user_id: int):
    status = presence_status(user_id)
    return Response({'status': status})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def contact_list_view(request):
    try:
        user = request.user
        # Efficiently fetch all rooms and their latest message in one go
        from django.db.models import Prefetch, Count, Case, When, IntegerField
        from ...models import Room, Message, Streak
        
        # Room qs with unread count annotated
        rooms = Room.objects.filter(Q(caller=user) | Q(receiver=user)) \
            .select_related('caller__profile', 'receiver__profile') \
            .annotate(
                unread_count=Count('messages', filter=Q(messages__is_seen=False) & ~Q(messages__sender=user)),
                last_msg_time=Max('messages__created_at')
            ) \
            .filter(last_msg_time__isnull=False) \
            .prefetch_related(Prefetch('messages', queryset=Message.objects.order_by('-created_at'), to_attr='latest_msgs')) \
            .order_by('-last_msg_time')

        # Prefetch all relevant streaks for these users to avoid N+1 in the loop
        other_user_ids = [r.receiver_id if r.caller_id == user.id else r.caller_id for r in rooms]
        
        streaks = {
            (min(user.id, s.user1_id, s.user2_id), max(user.id, s.user1_id, s.user2_id)): s
            for s in Streak.objects.filter(
                (Q(user1=user) & Q(user2_id__in=other_user_ids)) | 
                (Q(user2=user) & Q(user1_id__in=other_user_ids))
            )
        }

        contacts_data = []
        seen_users = set()

        for room in rooms:
            other_user = room.receiver if room.caller == user else room.caller
            if other_user.id in seen_users:
                continue
                
            last_msg = room.latest_msgs[0] if room.latest_msgs else None
            if not last_msg:
                continue
                
            seen_users.add(other_user.id)
            
            # Attach transient data for serializer
            other_user.last_message = last_msg.content
            other_user.last_message_type = last_msg.type
            other_user.last_timestamp = last_msg.created_at
            other_user.unread_count = room.unread_count

            # Attach Streak Info from our pre-fetched dictionary
            u1_id, u2_id = (user.id, other_user.id) if user.id < other_user.id else (other_user.id, user.id)
            streak = streaks.get((u1_id, u2_id))
            
            other_user.streak_count = streak.streak_count if streak else 0
            other_user.streak_last_interaction = streak.last_interaction_date if streak else None
            
            contacts_data.append(other_user)
            
        return Response(ContactSerializer(contacts_data, many=True, context={'request': request}).data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in contact_list_view: {e}")
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
        return Response(RoomSerializer(room).data, status=201)
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

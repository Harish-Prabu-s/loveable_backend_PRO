from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from ...serializers import GameSerializer
from .services import list_active_games, get_icebreaker_prompt
from .matchmaking_service import matchmake_user
from api.models import GameRoom, InteractiveGameSession, PlayerState
from django.contrib.auth.models import User

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_games_view(request):
    qs = list_active_games()
    return Response(GameSerializer(qs, many=True).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def icebreaker_prompt_view(request, kind: str):
    data = get_icebreaker_prompt(kind)
    return Response(data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def matchmake_view(request):
    game_type = request.data.get('game_type', 'truth_or_dare')
    mode = request.data.get('mode', '2p')
    
    from .matchmaking_redis import matchmake_user_redis
    try:
        result = matchmake_user_redis(request.user, mode, game_type)
        return Response(result)
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def leave_matchmake_view(request):
    from .matchmaking_redis import leave_matchmaking_redis
    result = leave_matchmaking_redis(request.user.id)
    return Response(result)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_invite_view(request):
    target_id = request.data.get('target_user_id')
    game_mode = request.data.get('game_type', 'truth_dare')
    
    from .invite_service import send_game_invite
    result = send_game_invite(request.user, target_id, game_mode)
    
    if result['status'] == 'success':
        return Response(result)
    return Response(result, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_invite_view(request):
    notification_id = request.data.get('notification_id')
    action = request.data.get('action', 'accept')
    
    from .invite_service import respond_game_invite
    result = respond_game_invite(notification_id, request.user, action)
    
    if result['status'] == 'success':
        return Response(result)
    return Response(result, status=400)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_game_room_view(request):
    import uuid
    
    room_type = request.data.get('room_type', 'group')
    target_id = request.data.get('target_user_id')
    
    room_code = uuid.uuid4().hex[:8]
    room = GameRoom.objects.create(
        host=request.user,
        room_code=room_code,
        room_type=room_type,
        status='waiting' if not target_id else 'active'
    )
    
    # Create the interactive session
    session = InteractiveGameSession.objects.create(
        room=room,
        current_state='Waiting'
    )
    
    # Add host as first player
    PlayerState.objects.create(
        session=session,
        user=request.user,
        is_connected=True
    )
    
    # If a target user is specified (e.g. couple mode), add them too
    if target_id:
        try:
            target_user = User.objects.get(id=target_id)
            PlayerState.objects.create(
                session=session,
                user=target_user,
                is_connected=True # Treat as connected for direct invite
            )
        except User.DoesNotExist:
            pass
            
    return Response({
        'id': room.id, 
        'room_code': room_code, 
        'room_type': room.room_type,
        'session_id': session.id
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def join_room_view(request):
    room_code = request.data.get('room_code')
    if not room_code:
        return Response({'status': 'error', 'message': 'Room code required'}, status=400)
    
    try:
        room = GameRoom.objects.get(room_code=room_code)
        session = InteractiveGameSession.objects.get(room=room)
        
        # Add player if not already in
        player, created = PlayerState.objects.get_or_create(
            session=session,
            user=request.user,
            defaults={'is_connected': True}
        )
        
        if not created:
            player.is_connected = True
            player.save()
            
        return Response({
            'id': room.id,
            'room_code': room.room_code,
            'room_type': room.room_type,
            'session_id': session.id,
            'game_type': session.game_type if hasattr(session, 'game_type') else 'truth_dare'
        })
    except GameRoom.DoesNotExist:
        return Response({'status': 'error', 'message': 'Invalid room code'}, status=404)
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)

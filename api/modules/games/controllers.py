from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from ...serializers import GameSerializer
from .services import list_active_games, get_icebreaker_prompt
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
def create_game_room_view(request):
    import uuid
    
    room_type = request.data.get('room_type', 'group')
    target_id = request.data.get('target_user_id')
    
    room_code = uuid.uuid4().hex[:8]
    room = GameRoom.objects.create(
        host=request.user,
        room_code=room_code,
        room_type=room_type,
        status='waiting'
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
                is_connected=False
            )
        except User.DoesNotExist:
            pass
            
    return Response({
        'id': room.id, 
        'room_code': room_code, 
        'room_type': room.room_type,
        'session_id': session.id
    })

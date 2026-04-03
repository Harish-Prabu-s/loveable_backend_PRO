from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import add_close_friend_service, remove_close_friend_service, list_close_friends_service

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_close_friend(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    cf, msg = add_close_friend_service(request.user, user_id)
    if not cf:
        return Response({'success': False, 'error': msg}, status=400)
    return Response({'success': True, 'message': msg})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def remove_close_friend(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    success, msg = remove_close_friend_service(request.user, user_id)
    if not success:
        return Response({'success': False, 'error': msg}, status=400)
    return Response({'success': True, 'message': msg})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_close_friends(request):
    data = list_close_friends_service(request.user, request)
    return Response(data)

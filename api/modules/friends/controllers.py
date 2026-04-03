from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import send_friend_request, accept_friend_request, reject_friend_request

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_request(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    req, msg = send_friend_request(request.user, user_id)
    if not req:
        return Response({'error': msg}, status=400)
    return Response({'status': msg, 'request_id': req.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_accept(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    req, msg = accept_friend_request(request.user, user_id)
    if not req:
        return Response({'error': msg}, status=400)
    return Response({'status': msg})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def friend_reject(request):
    user_id = request.data.get('user_id')
    if not user_id:
        return Response({'error': 'user_id is required'}, status=400)
    req, msg = reject_friend_request(request.user, user_id)
    if not req:
        return Response({'error': msg}, status=400)
    return Response({'status': msg})

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .services import archive_content, unarchive_content, delete_content, get_archived_content

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def archive_view(request):
    ctype = request.data.get('type')
    cid = request.data.get('id')
    if not ctype or not cid:
        return Response({'error': 'type and id are required'}, status=400)
    
    res = archive_content(request.user, ctype, int(cid))
    if 'error' in res:
        return Response(res, status=400)
    return Response(res)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unarchive_view(request):
    ctype = request.data.get('type')
    cid = request.data.get('id')
    if not ctype or not cid:
        return Response({'error': 'type and id are required'}, status=400)
    
    res = unarchive_content(request.user, ctype, int(cid))
    if 'error' in res:
        return Response(res, status=400)
    return Response(res)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_view(request):
    ctype = request.data.get('type')
    cid = request.data.get('id')
    if not ctype or not cid:
        return Response({'error': 'type and id are required'}, status=400)
    
    res = delete_content(request.user, ctype, int(cid))
    if 'error' in res:
        return Response(res, status=400)
    return Response(res)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_archived_view(request):
    ctype = request.query_params.get('type')
    if not ctype:
        return Response({'error': 'type is required'}, status=400)
    
    data = get_archived_content(request.user, ctype, request=request)
    if isinstance(data, dict) and 'error' in data:
        return Response(data, status=400)
    return Response(data)

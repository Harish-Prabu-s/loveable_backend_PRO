from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .algorithm import get_personalized_feed
from .engagement import (
    increment_post_view, increment_reel_view,
    increment_post_share, increment_reel_share,
    recalculate_post_score, recalculate_reel_score,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feed_view(request):
    """
    GET /api/feed/
    Returns a personalized mixed feed of posts and reels.
    Query params:
      ?page=1&limit=20&type=mixed|posts|reels
    """
    try:
        page  = int(request.GET.get('page', 1))
        limit = int(request.GET.get('limit', 20))
    except ValueError:
        page, limit = 1, 20

    content_type = request.GET.get('type', 'mixed')
    if content_type not in ('mixed', 'posts', 'reels'):
        content_type = 'mixed'

    items = get_personalized_feed(request.user, limit=limit, page=page, content_type=content_type)

    # Serialize results inline (keeps this self-contained; no circular import)
    from api.serializers import PostSerializer, ReelSerializer
    results = []
    for item in items:
        if item['type'] == 'post':
            data = PostSerializer(item['obj'], context={'request': request}).data
        else:
            data = ReelSerializer(item['obj'], context={'request': request}).data
        data['_feed_type']  = item['type']
        data['_feed_score'] = round(item['score'], 4)
        results.append(data)

    return Response({'results': results, 'page': page, 'limit': limit, 'type': content_type})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_post_view(request, post_id: int):
    """POST /api/feed/posts/<post_id>/view/"""
    increment_post_view(post_id)
    return Response({'status': 'ok'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def record_reel_view(request, reel_id: int):
    """POST /api/feed/reels/<reel_id>/view/"""
    increment_reel_view(reel_id)
    return Response({'status': 'ok'})

"""
Recommendation Feed API
========================
GET /api/rec/feed/ — serves the pre-computed personalized feed from Redis.

This endpoint does ZERO MySQL queries. It reads only from the Redis feed
cache populated by the `rebuild_user_feeds` Celery Beat task (Task 3).

If the Redis key is missing (new user, or cache expired before rebuild),
it falls back to the existing feed algorithm for a graceful degradation.
"""

import json
import logging
import redis
from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from api.models import Post, Reel
from api.serializers import PostSerializer, ReelSerializer

logger = logging.getLogger(__name__)

_cache_redis = None

def _get_cache_redis():
    global _cache_redis
    if _cache_redis is None:
        _cache_redis = redis.Redis.from_url(
            settings.REDIS_CACHE_URL,
            decode_responses=True,
        )
    return _cache_redis

class RecommendedFeedView(APIView):
    """
    GET /api/rec/feed/
    
    Query Params:
    - page (int): Default 1
    - limit (int): Default 20
    - content_type (str): 'post' or 'reel' or 'all' (default 'all')
    
    Reads from Redis for order, then queries MySQL to serialize full objects.
    Returns standard DRF paginated structure.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_id = request.user.id
        
        try:
            page = int(request.query_params.get('page', 1))
            limit = int(request.query_params.get('limit', 20))
        except ValueError:
            page = 1
            limit = 20
            
        content_type_filter = request.query_params.get('content_type', 'all')

        try:
            r = _get_cache_redis()
            feed_json = r.get(f'feed:{user_id}:page:{page}')
            
            raw_items = []
            if feed_json:
                raw_items = json.loads(feed_json)
                next_page_json = r.get(f'feed:{user_id}:page:{page + 1}')
                has_next = next_page_json is not None
            else:
                # Fallback
                from api.modules.feed.algorithm import get_personalized_feed
                fallback_items = get_personalized_feed(
                    request.user, limit=20, page=page, content_type='all' if content_type_filter == 'all' else f"{content_type_filter}s"
                )
                raw_items = [{'content_id': item['id'], 'type': item['type']} for item in fallback_items]
                has_next = False

            if content_type_filter != 'all':
                raw_items = [item for item in raw_items if item['type'] == content_type_filter]
                
            post_ids = [item['content_id'] for item in raw_items if item['type'] == 'post']
            reel_ids = [item['content_id'] for item in raw_items if item['type'] == 'reel']
            
            # Fetch full objects
            posts = {p.id: p for p in Post.objects.filter(id__in=post_ids).select_related('user__profile', 'audio')}
            reels = {r.id: r for r in Reel.objects.filter(id__in=reel_ids).select_related('user__profile', 'audio')}
            
            final_items = []
            for item in raw_items:
                if item['type'] == 'post' and item['content_id'] in posts:
                    ser = PostSerializer(posts[item['content_id']], context={'request': request}).data
                    ser['_rec_type'] = 'post'
                    final_items.append(ser)
                elif item['type'] == 'reel' and item['content_id'] in reels:
                    ser = ReelSerializer(reels[item['content_id']], context={'request': request}).data
                    ser['_rec_type'] = 'reel'
                    final_items.append(ser)

            return Response({
                'source': 'recommendation' if feed_json else 'fallback',
                'page': page,
                'limit': limit,
                'has_next': has_next,
                'next': f'/api/rec/feed/?page={page+1}&limit={limit}&content_type={content_type_filter}' if has_next else None,
                'results': final_items,
                'count': len(final_items),
            })

        except Exception as e:
            logger.error(f'Feed error for user {user_id}: {e}')
            return Response(
                {'source': 'error', 'results': [], 'count': 0, 'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

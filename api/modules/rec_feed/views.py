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

logger = logging.getLogger(__name__)

# Lazy-initialized Redis connection for feed cache
_cache_redis = None


def _get_cache_redis():
    """Get Redis connection for the feed cache (DB 3)."""
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

    Returns the user's personalized feed (up to 20 items).

    Response format:
    {
        "source": "recommendation" | "fallback",
        "items": [
            {
                "content_id": 123,
                "type": "reel",
                "creator_id": 45,
                "caption": "...",
                "created_at": "2026-08-18T...",
                "engagement_score": 42.5,
                "view_count": 100,
                "share_count": 5
            },
            ...
        ]
    }
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

        try:
            r = _get_cache_redis()
            feed_json = r.get(f'feed:{user_id}:page:{page}')

            if feed_json:
                items = json.loads(feed_json)
                
                # Check if next page exists
                next_page_json = r.get(f'feed:{user_id}:page:{page + 1}')
                has_next = next_page_json is not None
                
                return Response({
                    'source': 'recommendation',
                    'page': page,
                    'limit': limit,
                    'has_next': has_next,
                    'next_page': page + 1 if has_next else None,
                    'items': items,
                    'count': len(items),
                })

        except redis.RedisError as e:
            logger.error(f'Redis error reading feed for user {user_id}: {e}')
            # Fall through to fallback

        except (json.JSONDecodeError, TypeError) as e:
            logger.error(f'Invalid feed JSON for user {user_id}: {e}')
            # Fall through to fallback

        # ── Fallback: use the existing feed algorithm ──────────────────────
        # This ensures new users and users without cached feeds still get
        # a reasonable feed while the recommendation engine warms up.
        try:
            from api.modules.feed.algorithm import get_personalized_feed

            fallback_items = get_personalized_feed(
                request.user, limit=20, page=1, content_type='reels',
            )

            items = []
            for item in fallback_items:
                obj = item['obj']
                items.append({
                    'content_id': item['id'],
                    'type': item['type'],
                    'creator_id': obj.user_id,
                    'caption': (obj.caption or '')[:200],
                    'created_at': obj.created_at.isoformat() if obj.created_at else None,
                    'engagement_score': getattr(obj, 'engagement_score', 0.0),
                    'view_count': getattr(obj, 'view_count', 0),
                    'share_count': getattr(obj, 'share_count', 0),
                })

            return Response({
                'source': 'fallback',
                'page': page,
                'limit': limit,
                'has_next': False,
                'next_page': None,
                'items': items,
                'count': len(items),
            })

        except Exception as e:
            logger.error(f'Fallback feed also failed for user {user_id}: {e}')
            return Response(
                {'source': 'error', 'items': [], 'count': 0,
                 'error': 'Feed temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

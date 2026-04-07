from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from ...models import Hashtag, Post, Reel, Story


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def trending_hashtags(request):
    """Return top 20 trending hashtags by usage count."""
    tags = Hashtag.objects.order_by('-usage_count')[:20]
    data = [{'id': t.id, 'name': t.name, 'usage_count': t.usage_count} for t in tags]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_hashtags(request):
    """Search hashtags by prefix."""
    q = request.query_params.get('q', '').strip().lstrip('#')
    if not q:
        return Response([])
    tags = Hashtag.objects.filter(name__icontains=q).order_by('-usage_count')[:15]
    data = [{'id': t.id, 'name': t.name, 'usage_count': t.usage_count} for t in tags]
    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def hashtag_content(request, tag_name):
    """Get posts and reels for a specific hashtag."""
    tag_name = tag_name.lstrip('#').lower()
    try:
        tag = Hashtag.objects.get(name=tag_name)
    except Hashtag.DoesNotExist:
        return Response({'posts': [], 'reels': [], 'tag': None})

    posts = tag.posts.filter(is_archived=False).order_by('-created_at')[:30]
    reels = tag.reels.filter(is_archived=False).order_by('-created_at')[:30]

    post_data = []
    for p in posts:
        img_url = request.build_absolute_uri(p.image.url) if p.image else None
        post_data.append({'id': p.id, 'type': 'post', 'thumbnail': img_url, 'caption': p.caption})

    reel_data = []
    for r in reels:
        vid_url = request.build_absolute_uri(r.video_url.url) if r.video_url else None
        reel_data.append({'id': r.id, 'type': 'reel', 'thumbnail': vid_url, 'caption': r.caption})

    return Response({
        'tag': {'id': tag.id, 'name': tag.name, 'usage_count': tag.usage_count},
        'posts': post_data,
        'reels': reel_data,
    })


def sync_hashtags(text: str, content_obj, field_name='hashtags'):
    """Parse #hashtags from text and associate with content_obj. Creates new tags if needed."""
    import re
    tags_found = re.findall(r'#(\w+)', text or '')
    tag_objs = []
    for tag_name in set(t.lower() for t in tags_found):
        tag, created = Hashtag.objects.get_or_create(name=tag_name)
        if not created:
            Hashtag.objects.filter(pk=tag.pk).update(usage_count=tag.usage_count + 1)
        tag_objs.append(tag)
    getattr(content_obj, field_name).set(tag_objs)

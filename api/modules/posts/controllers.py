from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from .services import get_feed, create_post, toggle_like, delete_post
from ...models import PostLike


from ...utils import get_absolute_media_url

def _serialize_post(post, request_user, request=None):
    """Serialize a Post instance efficiently using annotated data."""
    p = getattr(post.user, 'profile', None)
    image_url = get_absolute_media_url(post.image, request)
    photo_url = get_absolute_media_url(p.photo, request) if p else None

    # Use annotated values or fallbacks if not available (e.g. for single post)
    likes_count = getattr(post, 'likes_count', PostLike.objects.filter(post=post).count())
    comments_count = getattr(post, 'comments_count', post.comments.count())
    is_liked = getattr(post, 'is_liked', PostLike.objects.filter(post=post, user=request_user).exists())

    return {
        'id': post.id,
        'user': post.user.id,
        'profile_id': p.id if p else None,
        'display_name': p.display_name if p else '',
        'username': p.display_name if p else '',
        'photo': photo_url,
        'gender': p.gender if p else '',
        'caption': post.caption,
        'image': image_url,
        'likes_count': likes_count,
        'comments_count': comments_count,
        'is_liked': is_liked,
        'is_owner': post.user == request_user,
        'created_at': post.created_at.isoformat(),
        'reposted_from': post.reposted_from_id,
        'parent_user': {
            'id': post.reposted_from.user.id,
            'user_id': post.reposted_from.user.id,
            'username': post.reposted_from.user.username,
            'display_name': getattr(post.reposted_from.user, 'profile', post.reposted_from.user).display_name if hasattr(post.reposted_from.user, 'profile') else post.reposted_from.user.username,
            'photo': get_absolute_media_url(post.reposted_from.user.profile.photo, request) if hasattr(post.reposted_from.user, 'profile') and post.reposted_from.user.profile.photo else None,
        } if post.reposted_from else None,
        'mentioned_users': [{
            'id': u.id,
            'username': u.username,
            'display_name': getattr(u, 'profile', u).display_name if hasattr(u, 'profile') else u.username,
            'photo': get_absolute_media_url(u.profile.photo, request) if hasattr(u, 'profile') and u.profile.photo else None,
        } for u in post.mentions.all()]
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def feed_view(request):
    posts = get_feed(request.user)
    data = [_serialize_post(p, request.user, request) for p in posts]
    return Response(data)


from rest_framework.parsers import MultiPartParser, FormParser

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def create_post_view(request):
    print(f"DEBUG Post Upload: data={request.data}, files={request.FILES}")
    try:
        caption = request.data.get('caption', '').strip()
        
        image = None
        if 'image' in request.FILES:
            image = request.FILES['image']
        elif 'image' in request.data:
            image = request.data['image']


        if not caption and not image:
            return Response({'error': 'caption or image required', 'debug_files': list(request.FILES.keys()), 'debug_data': list(request.data.keys())}, status=400)

        visibility = request.data.get('visibility', 'all')
        mentions = request.data.get('mentions', [])
        if isinstance(mentions, str):
            try:
                import json
                mentions = json.loads(mentions)
            except:
                mentions = [int(m) for m in mentions.split(',') if m.isdigit()]
        
        post = create_post(request.user, caption, image, visibility, mentions=mentions)
        return Response(_serialize_post(post, request.user, request), status=201)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return Response({'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def like_view(request, post_id: int):
    result = toggle_like(post_id, request.user)
    if result is None:
        return Response({'error': 'post not found'}, status=404)
    return Response(result)

    return Response(result)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def comment_view(request, post_id: int):
    text = request.data.get('text', '').strip()
    reply_to_id = request.data.get('reply_to_id')
    if not text:
        return Response({'error': 'text required'}, status=400)
    
    try:
        from .services import add_comment
        comment = add_comment(post_id, request.user, text, reply_to_id)
        if not comment:
            return Response({'error': 'post not found'}, status=404)
        return Response({'success': True, 'id': comment.id}, status=201)
    except Exception as e:
        return Response({'error': str(e)}, status=500)
    except Post.DoesNotExist:
        return Response({'error': 'post not found'}, status=404)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def share_post_view(request, post_id: int):
    from ...models import Post, User, Message, Room
    target_user_id = request.data.get('target_user_id')
    if not target_user_id:
        return Response({'error': 'target_user_id required'}, status=400)
    
    try:
        from .services import share_post
        success = share_post(post_id, request.user, target_user_id, request)
        if not success:
            return Response({'error': 'post or user not found'}, status=404)
        return Response({'success': True})
    except Exception as e:
        return Response({'error': str(e)}, status=500)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def list_comments_view(request, post_id: int):
    if request.method == 'POST':
        return comment_view(request._request, post_id)
    from ...models import Post, PostComment
    from ...utils import get_absolute_media_url
    try:
        post = Post.objects.get(pk=post_id)
        comments = post.comments.all().select_related('user__profile').order_by('-created_at')
        
        comment_dict = {}
        root_comments = []
        
        for c in comments:
            p = getattr(c.user, 'profile', None)
            comment_dict[c.id] = {
                'id': c.id,
                'user': c.user.id,
                'display_name': p.display_name if p else '',
                'photo': get_absolute_media_url(p.photo, request) if p and p.photo else None,
                'text': c.text,
                'created_at': c.created_at.isoformat(),
                'reply_to': c.reply_to_id,
                'replies': []
            }
            
        for c in comments:
            if c.reply_to_id and c.reply_to_id in comment_dict:
                comment_dict[c.reply_to_id]['replies'].append(comment_dict[c.id])
            else:
                root_comments.append(comment_dict[c.id])
                
        return Response(root_comments)
    except Post.DoesNotExist:
        return Response({'error': 'post not found'}, status=404)

@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_post_view(request, post_id: int):
    deleted = delete_post(post_id, request.user)
    if not deleted:
        return Response({'error': 'post not found or permission denied'}, status=404)
    return Response(status=204)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def repost_view(request, post_id: int):
    from .services import repost_post
    post = repost_post(request.user, post_id)
    if not post:
        return Response({'error': 'post not found'}, status=404)
        
    # Notify original owner
    if post.reposted_from and post.reposted_from.user != request.user:
        from ..notifications.repost_service import notify_content_repost
        notify_content_repost(request.user, post.reposted_from.user, 'post', post.id)

    return Response(_serialize_post(post, request.user, request), status=201)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def view_post_view(request, post_id: int):
    from ...models import Post, PostView
    try:
        post = Post.objects.get(pk=post_id)
        PostView.objects.get_or_create(post=post, viewer=request.user)
        return Response({'success': True})
    except Post.DoesNotExist:
        return Response({'error': 'Post not found'}, status=404)

from ...models import Post, PostLike
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


from django.db import models

def get_feed(user):
    """Return all posts optimized with counts and like status."""
    from django.db.models import Count, Exists, OuterRef, F
    
    # Subquery to check if current user liked the post
    is_liked_subquery = PostLike.objects.filter(
        post=OuterRef('pk'),
        user=user
    )
    
    return Post.objects.select_related('user__profile').annotate(
        lcount=Count('likes', distinct=True),
        ccount=Count('comments', distinct=True),
        is_liked=Exists(is_liked_subquery)
    ).annotate(
        popularity_score=(F('lcount') * 2) + (F('ccount') * 5)
    ).filter(
        models.Q(is_archived=False) & (
            models.Q(visibility='all') | 
            models.Q(user=user) | 
            (models.Q(visibility='close_friends') & models.Q(user__close_friends__close_friend=user))
        )
    ).order_by('-popularity_score', '-created_at').distinct()


import base64
import re
import uuid

def create_post(user, caption: str, image=None, visibility='all'):
    """Create and return a new post, optionally saving an uploaded image file."""
    post = Post(user=user, caption=caption, visibility=visibility)
    if image:
        if isinstance(image, str):
            # Try parsing it as a base64 data URI
            match = re.match(r'data:(image/\w+);base64,(.+)', image)
            if match:
                mime_type = match.group(1)
                base64_data = match.group(2)
                ext = mime_type.split('/')[-1]
                filename = f"posts/{user.id}_{uuid.uuid4().hex[:8]}.{ext}"
                try:
                    file_data = base64.b64decode(base64_data)
                    path = default_storage.save(filename, ContentFile(file_data))
                    post.image = path
                except Exception as e:
                    print(f"Error decoding base64 image: {e}")
            else:
                print("Image string did not match expected base64 format.")
        else:
            filename = f"posts/{user.id}_{image.name}"
            path = default_storage.save(filename, ContentFile(image.read()))
            post.image = path
    post.save()
    
    # Notify Close Friends
    from ..notifications.services import notify_close_friends_of_content
    from ..notifications.utils import handle_mentions
    notify_close_friends_of_content(user, 'post', post.id)
    handle_mentions(caption, user, 'post', post.id, obj=post)
    
    return post


def toggle_like(post_id: int, user):
    """Toggle like on a post and handle notifications."""
    from ..notifications.services import create_notification
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    
    try:
        post = Post.objects.select_related('user').get(id=post_id)
    except Post.DoesNotExist:
        return None

    like, created = PostLike.objects.get_or_create(post=post, user=user)
    if not created:
        like.delete()
        is_liked = False
    else:
        is_liked = True
        # Notify owner
        if post.user != user:
            profile = getattr(user, 'profile', None)
            sender_name = profile.display_name if profile else user.username
            create_notification(
                recipient=post.user,
                actor=user,
                notification_type='post_like',
                message=f"{sender_name} liked your post!",
                object_id=post.id
            )
            tokens = _get_user_tokens(post.user.id)
            if tokens:
                send_push_notification(tokens, title="New Like!", body=f"{sender_name} liked your post!", data={'type': 'post_like', 'post_id': post.id})

    likes_count = PostLike.objects.filter(post=post).count()
    return {'is_liked': is_liked, 'likes_count': likes_count}

def add_comment(post_id: int, user, text: str):
    """Add a comment and notify post owner."""
    from ...models import PostComment
    from ..notifications.services import create_notification
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    
    try:
        post = Post.objects.select_related('user').get(id=post_id)
        comment = PostComment.objects.create(post=post, user=user, text=text)
        
        # Process Mentions
        from ..notifications.utils import handle_mentions
        handle_mentions(text, user, 'post_comment', post.id)
        
        # Notify owner
        if post.user != user:
            profile = getattr(user, 'profile', None)
            sender_name = profile.display_name if profile else user.username
            create_notification(
                recipient=post.user,
                actor=user,
                notification_type='post_comment',
                message=f"{sender_name} commented: {text[:30]}...",
                object_id=post.id
            )
            tokens = _get_user_tokens(post.user.id)
            if tokens:
                send_push_notification(tokens, title="New Comment!", body=f"{sender_name} commented: {text[:30]}...", data={'type': 'post_comment', 'post_id': post.id})
        
        return comment
    except Post.DoesNotExist:
        return None


def delete_post(post_id: int, user):
    """Delete a post. Returns True if deleted, False if not owner or not found."""
    try:
        post = Post.objects.get(id=post_id, user=user)
        post.delete()
        return True
    except Post.DoesNotExist:
        return False

def archive_post(post_id: int, user):
    """Archive a post."""
    try:
        post = Post.objects.get(id=post_id, user=user)
        post.is_archived = True
        post.save(update_fields=['is_archived'])
        return True
    except Post.DoesNotExist:
        return False
def share_post(post_id: int, user, target_user_id: int, request=None):
    """Share a post to another user via chat and handle notifications."""
    from ...models import User, Message, Room
    from ..chat.services import get_or_create_room
    from ..notifications.services import create_notification
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    from ...utils import get_absolute_media_url
    
    try:
        post = Post.objects.get(pk=post_id)
        target_user = User.objects.get(pk=target_user_id)
        
        # Create/Find Chat Room (using 'audio' as default type for new rooms if needed)
        room = get_or_create_room(user, target_user.id, 'audio')
        
        # Create Message for sharing
        msg_media_url = get_absolute_media_url(post.image, request)
        Message.objects.create(
            room=room,
            sender=user,
            content=f"[POST_SHARE:{post.id}]",
            type='post_share',
            media_url=msg_media_url
        )

        # Notify recipient
        profile = getattr(user, 'profile', None)
        sender_name = profile.display_name if profile else user.username
        
        create_notification(
            recipient=target_user,
            actor=user,
            notification_type='post_share',
            message=f"{sender_name} shared a post with you.",
            object_id=post.id
        )

        tokens = _get_user_tokens(target_user.id)
        if tokens:
            send_push_notification(
                tokens, 
                title="Shared Post", 
                body=f"{sender_name} shared a post with you.",
                data={'type': 'post_share', 'post_id': post.id, 'from_user_id': user.id}
            )
        
        return True
    except (Post.DoesNotExist, User.DoesNotExist):
        return False

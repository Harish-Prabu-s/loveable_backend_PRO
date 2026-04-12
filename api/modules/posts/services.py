from ...models import Post, PostLike
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


from django.db import models

def get_feed(user, search: str = None):
    """Return all posts optimized with counts and like status."""
    from django.db.models import Count, Exists, OuterRef, F
    
    # Subquery to check if current user liked the post
    is_liked_subquery = PostLike.objects.filter(
        post=OuterRef('pk'),
        user=user
    )
    
    qs = Post.objects.select_related('user__profile').annotate(
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
    )

    if search:
        search = search.lower().strip()
        if search.startswith('#'):
            qs = qs.filter(hashtags__name__icontains=search.lstrip('#'))
        else:
            qs = qs.filter(models.Q(caption__icontains=search) | models.Q(hashtags__name__icontains=search))

    return qs.order_by('-popularity_score', '-created_at').distinct()


import base64
import re
import uuid

def create_post(user, caption: str, image=None, cover_image=None, visibility='all', mentions=None, additional_images=None, audio_id=None, audio_meta=None, audio_start_sec=0):
    """Create and return a new post, optionally saving an uploaded image file and processing mentions."""
    from ...models import PostImage, Audio
    
    post = Post(user=user, caption=caption, visibility=visibility)
    post.audio_start_sec = int(audio_start_sec or 0)
    
    # Save primary image
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
            filename = f"posts/{user.id}_{uuid.uuid4().hex[:8]}_{image.name}"
            path = default_storage.save(filename, ContentFile(image.read()))
            post.image = path

    # Save cover image
    if cover_image:
        filename = f"posts/covers/{user.id}_{uuid.uuid4().hex[:8]}_{getattr(cover_image, 'name', 'cover.jpg')}"
        path = default_storage.save(filename, ContentFile(cover_image.read() if hasattr(cover_image, 'read') else cover_image))
        post.cover_image = path
    
    # Handle Audio
    if audio_id:
        try:
            # First try as integer ID
            audio = Audio.objects.get(pk=audio_id)
            post.audio = audio
        except (Audio.DoesNotExist, ValueError):
            # If not found or not a number, it's an external track. Wait for audio_meta
            pass

    if not post.audio and audio_meta and isinstance(audio_meta, dict):
        try:
            title = audio_meta.get('title', 'Original Audio')
            artist = audio_meta.get('artist', 'Unknown')
            cover_url = audio_meta.get('coverArt', '')
            ext_url = audio_meta.get('url', '')
            
            audio, created = Audio.objects.get_or_create(
                title=title, artist=artist,
                defaults={'created_by': user, 'cover_image_url': cover_url}
            )
            
            if created and ext_url:
                audio.file_url = ext_url
                audio.save()
            post.audio = audio
        except Exception as e:
            print(f"Error linking audio to post from meta: {e}")

    post.save()
    
    # Handle Additional Images (Multi-image posts)
    if additional_images:
        for index, img in enumerate(additional_images):
            try:
                img_filename = f"posts/{user.id}_{uuid.uuid4().hex[:8]}_{getattr(img, 'name', 'img.jpg')}"
                img_path = default_storage.save(img_filename, ContentFile(img.read() if hasattr(img, 'read') else img))
                PostImage.objects.create(post=post, image=img_path, order=index + 1)
            except Exception as e:
                print(f"Error saving additional image {index}: {e}")

    # Notify Close Friends, process mentions
    from ..notifications.services import notify_close_friends_of_content
    from ..notifications.utils import handle_mentions
    notify_close_friends_of_content(user, 'post', post.id)
    handle_mentions(caption, user, 'post', post.id, obj=post, explicit_mentions=mentions)
    
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

def add_comment(post_id: int, user, text: str, reply_to_id: int = None):
    """Add a comment and notify post owner or reply target."""
    from ...models import PostComment
    from ..notifications.services import create_notification
    from ..notifications.push_service import send_push_notification, _get_user_tokens
    
    try:
        post = Post.objects.select_related('user').get(id=post_id)
        comment = PostComment.objects.create(post=post, user=user, text=text, reply_to_id=reply_to_id)
        
        # Process Mentions
        from ..notifications.utils import handle_mentions
        handle_mentions(text, user, 'post_comment', post.id)
        
        
        profile = getattr(user, 'profile', None)
        sender_name = profile.display_name if profile else user.username

        # Notify owner
        if post.user != user and not reply_to_id:
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
                
        # Notify reply target
        if reply_to_id and comment.reply_to and comment.reply_to.user != user:
            target_user = comment.reply_to.user
            create_notification(
                recipient=target_user,
                actor=user,
                notification_type='post_comment_reply',
                message=f"{sender_name} replied to your comment: {text[:30]}...",
                object_id=post.id
            )
            tokens = _get_user_tokens(target_user.id)
            if tokens:
                send_push_notification(tokens, title="New Reply!", body=f"{sender_name} replied to your comment: {text[:30]}...", data={'type': 'post_comment', 'post_id': post.id})
        
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

        if tokens:
            send_push_notification(
                tokens, 
                title="Shared Post", 
                body=f"{sender_name} shared a post with you.",
                data={'type': 'post_share', 'post_id': post.id, 'from_user_id': user.id}
            )
        
        # Award coins for sharing (5 coins)
        try:
            from ...models import Wallet, CoinTransaction
            wallet, _ = Wallet.objects.get_or_create(user=user)
            wallet.coin_balance += 5
            wallet.save(update_fields=['coin_balance', 'updated_at'])
            CoinTransaction.objects.create(
                wallet=wallet,
                amount=5,
                type='credit',
                transaction_type='earned',
                description=f"Reward for sharing Post #{post.id}"
            )
        except Exception as e:
            print(f"Error awarding coins for sharing post: {e}")

        return True
    except (Post.DoesNotExist, User.DoesNotExist):
        return False

def repost_post(user, original_post_id):
    """Create a repost of an existing post if the user is mentioned.
    Returns (repost, error_code) tuple: error_code is None on success.
    """
    try:
        original = Post.objects.get(id=original_post_id)
    except Post.DoesNotExist:
        return None, 'deleted'

    # Block repost if post is archived by owner
    if original.is_archived:
        return None, 'deleted'

    # Only allow if mentioned or is the owner
    if not original.mentions.filter(id=user.id).exists() and original.user != user:
        return None, 'not_mentioned'

    repost = Post.objects.create(
        user=user,
        caption=original.caption,
        image=original.image,
        visibility='all',
        reposted_from=original
    )
    return repost, None

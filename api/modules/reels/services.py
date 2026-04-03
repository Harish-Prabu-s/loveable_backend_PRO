from ...models import Reel, ReelLike, ReelComment, User, Message
from ..chat.services import get_or_create_room

from django.db import models

def list_reels(user, limit: int = 10, page: int = 1, random_flag: bool = False):
    offset = (page - 1) * limit
    qs = Reel.objects.select_related('user__profile').filter(
        models.Q(is_archived=False) & (
            models.Q(visibility='all') | 
            models.Q(user=user) | 
            (models.Q(visibility='close_friends') & models.Q(user__close_friends__close_friend=user))
        )
    ).order_by('-created_at').distinct()[offset:offset+limit]
    
    qs = list(qs)
    
    if random_flag and page == 1:
        import random
        random.shuffle(qs)
        
    return qs

def create_reel(user, video_url: str, caption: str = '', visibility='all'):
    reel = Reel.objects.create(user=user, video_url=video_url, caption=caption, visibility=visibility)
    
    # Notify Close Friends
    from ..notifications.services import notify_close_friends_of_content
    from ..notifications.utils import handle_mentions
    notify_close_friends_of_content(user, 'reel', reel.id)
    handle_mentions(caption, user, 'reel', reel.id, obj=reel)
    
    return reel

def toggle_reel_like(reel_id: int, user: User):
    try:
        reel = Reel.objects.get(pk=reel_id)
        like, created = ReelLike.objects.get_or_create(reel=reel, user=user)
        if not created:
            like.delete()
            return {'liked': False, 'likes_count': reel.likes.count()}
        
        # Notify owner
        if reel.user != user:
            from ..notifications.services import create_notification
            from ..notifications.push_service import send_push_notification, _get_user_tokens
            
            profile = getattr(user, 'profile', None)
            sender_name = profile.display_name if profile else user.username
            
            create_notification(
                recipient=reel.user,
                actor=user,
                notification_type='reel_like',
                message=f"{sender_name} liked your reel!",
                object_id=reel.id
            )
            
            tokens = _get_user_tokens(reel.user_id)
            if tokens:
                send_push_notification(
                    tokens,
                    title="New Reel Like!",
                    body=f"{sender_name} liked your reel!",
                    data={'type': 'reel_like', 'reel_id': reel.id}
                )

        return {'liked': True, 'likes_count': reel.likes.count(), 'reel': reel}
    except Reel.DoesNotExist:
        return None

def add_reel_comment(reel_id: int, user: User, text: str):
    try:
        reel = Reel.objects.get(pk=reel_id)
        comment = ReelComment.objects.create(reel=reel, user=user, text=text)
        
        # Process Mentions
        from ..notifications.utils import handle_mentions
        handle_mentions(text, user, 'reel_comment', reel.id)
        
        return comment
    except Reel.DoesNotExist:
        return None

def get_reel_comments(reel_id: int):
    try:
        reel = Reel.objects.get(pk=reel_id)
        return reel.comments.all().select_related('user__profile').order_by('-created_at')
    except Reel.DoesNotExist:
        return None

def share_reel_to_chat(reel_id: int, sender: User, target_user_id: int):
    try:
        reel = Reel.objects.get(pk=reel_id)
        target_user = User.objects.get(pk=target_user_id)
        
        room = get_or_create_room(sender, target_user.id, 'audio')
        
        message = Message.objects.create(
            room=room,
            sender=sender,
            content=f"[REEL_SHARE:{reel.id}]",
            type='reel_share'
        )
        return {'success': True, 'target_user': target_user, 'reel': reel}
    except (Reel.DoesNotExist, User.DoesNotExist):
        return None

def delete_reel_service(reel_id: int, user: User):
    try:
        reel = Reel.objects.get(pk=reel_id)
        if reel.user != user:
            return {'error': 'permission denied', 'status': 403}
        
        if reel.video_url:
            try:
                reel.video_url.delete(save=False)
            except Exception:
                pass
            
        reel.delete()
        return {'success': True}
    except Reel.DoesNotExist:
        return {'error': 'reel not found', 'status': 404}

def archive_reel(reel_id: int, user: User):
    """Archive a reel."""
    try:
        reel = Reel.objects.get(pk=reel_id, user=user)
        reel.is_archived = True
        reel.save(update_fields=['is_archived'])
        return True
    except Reel.DoesNotExist:
        return False

def unarchive_reel(reel_id: int, user: User):
    """Unarchive a reel."""
    try:
        reel = Reel.objects.get(pk=reel_id, user=user)
        reel.is_archived = False
        reel.save(update_fields=['is_archived'])
        return True
    except Reel.DoesNotExist:
        return False

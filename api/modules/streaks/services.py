from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from ...models import Streak, StreakUpload, Follow, Notification, StreakComment, StreakLike, StreakReaction
from ...serializers import ProfileSerializer
from ...utils import get_absolute_media_url
from ..notifications.push_service import send_push_notification, _get_user_tokens

def get_user_streaks_service(user: User, request=None):
    # Get all streaks involving this user
    streaks = Streak.objects.filter(models.Q(user1=user) | models.Q(user2=user)).select_related('user1__profile', 'user2__profile')
    
    result = []
    for s in streaks:
        other_user = s.user2 if s.user1 == user else s.user1
        # skip if no profile
        if not hasattr(other_user, 'profile'):
            continue
        # Get latest active upload (last 24h) from other user
        from django.utils import timezone
        from datetime import timedelta
        day_ago = timezone.now() - timedelta(hours=24)
        latest_upload = StreakUpload.objects.filter(
            models.Q(user=other_user),
            models.Q(created_at__gte=day_ago) & (
                models.Q(visibility='all') |
                (models.Q(visibility='close_friends') & models.Q(user__close_friends__close_friend=user))
            )
        ).order_by('-created_at').first()

        result.append({
            'streak_id': s.id,
            'friend': ProfileSerializer(other_user.profile, context={'request': request}).data,
            'streak_count': s.streak_count,
            'last_interaction_date': s.last_interaction_date,
            'freezes_available': s.freezes_available,
            'latest_upload_id': latest_upload.id if latest_upload else None
        })
    return result

def upload_streak_service(user: User, media, media_type, visibility, caption: str = '', mentions=None):
    upload = StreakUpload.objects.create(
        user=user,
        media_url=media,
        media_type=media_type,
        visibility=visibility,
        caption=caption
    )
    
    # Increment streaks for mutual followers.
    followers = Follow.objects.filter(following=user).values_list('follower_id', flat=True)
    following = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    mutuals = set(followers).intersection(set(following))
    
    profile = getattr(user, 'profile', None)
    sender_name = profile.display_name if profile else user.username

    now = timezone.now()
    
    # Process Mentions (both parsed and explicit)
    from ..notifications.utils import handle_mentions
    handle_mentions(caption, user, 'streak', upload.id, obj=upload, explicit_mentions=mentions)

    for friend_id in mutuals:
        # Get or create streak between user and friend
        s = Streak.objects.filter(
            (models.Q(user1_id=user.id, user2_id=friend_id) | models.Q(user1_id=friend_id, user2_id=user.id))
        ).first()
        
        if not s:
            s = Streak.objects.create(user1_id=user.id, user2_id=friend_id, streak_count=1, last_interaction_date=now, last_uploader=user)
        else:
            if s.last_interaction_date and s.last_interaction_date.date() < now.date():
                s.streak_count += 1
            s.last_interaction_date = now
            s.last_uploader = user
            s.save()
            
        # Notify friend
        try:
            friend_user = User.objects.get(id=friend_id)
            from ..notifications.services import create_notification
            create_notification(
                recipient=friend_user,
                actor=user,
                notification_type='streak_upload',
                message=f"🔥 Your streak with {sender_name} increased!",
                object_id=upload.id
            )
            tokens = _get_user_tokens(friend_id)
            if tokens:
                send_push_notification(
                    tokens,
                    title="🔥 New Streak!",
                    body=f"Your streak with {sender_name} increased!",
                    data={'type': 'streak_upload', 'user_id': user.id}
                )
        except Exception:
            pass

    return upload, "Streak uploaded successfully"

def add_streak_comment(streak_upload_id: int, user: User, text: str):
    try:
        upload = StreakUpload.objects.get(pk=streak_upload_id)
        comment = StreakComment.objects.create(streak_upload=upload, user=user, text=text)
        
        # Notify owner
        if upload.user != user:
            from ..notifications.services import create_notification
            create_notification(
                recipient=upload.user,
                actor=user,
                notification_type='streak_comment',
                message=f"💬 {user.username} commented on your streak!",
                object_id=upload.id
            )
            
        return comment
    except StreakUpload.DoesNotExist:
        return None

def get_streak_comments(streak_upload_id: int):
    try:
        upload = StreakUpload.objects.get(pk=streak_upload_id)
        return StreakComment.objects.filter(streak_upload=upload).select_related('user__profile').order_by('-created_at')
    except StreakUpload.DoesNotExist:
        return None

def get_streak_upload_service(upload_id: int):
    try:
        return StreakUpload.objects.select_related('user__profile').get(pk=upload_id)
    except StreakUpload.DoesNotExist:
        return None

def toggle_streak_like(upload_id: int, user: User):
    try:
        upload = StreakUpload.objects.get(pk=upload_id)
        like = StreakLike.objects.filter(streak_upload=upload, user=user).first()
        if like:
            like.delete()
            return False, "Unliked"
        else:
            StreakLike.objects.create(streak_upload=upload, user=user)
            
            # Notify owner
            if upload.user != user:
                from ..notifications.services import create_notification
                from ..notifications.push_service import send_push_notification, _get_user_tokens
                
                profile = getattr(user, 'profile', None)
                sender_name = profile.display_name if profile else user.username
                
                create_notification(
                    recipient=upload.user,
                    actor=user,
                    notification_type='streak_like',
                    message=f"{sender_name} liked your streak!",
                    object_id=upload.id
                )
                
                tokens = _get_user_tokens(upload.user_id)
                if tokens:
                    send_push_notification(
                        tokens,
                        title="New Streak Like!",
                        body=f"{sender_name} liked your streak!",
                        data={'type': 'streak_like', 'upload_id': upload.id}
                    )
                    
            return True, "Liked"
    except StreakUpload.DoesNotExist:
        return None, "Not found"

def update_streak_count(u1, u2):
    from ...models import Streak
    s = Streak.objects.filter(
        (models.Q(user1=u1, user2=u2) | models.Q(user1=u2, user2=u1))
    ).first()
    if not s:
        s = Streak.objects.create(user1=u1, user2=u2, streak_count=0)
    
    # Count total fire reactions between these two users
    count = StreakReaction.objects.filter(
        (models.Q(user=u1, recipient=u2) | models.Q(user=u2, recipient=u1)),
        reaction_type='fire'
    ).count()
    s.streak_count = count
    s.last_interaction_date = timezone.now()
    if count > 0:
        s.last_uploader = u1 # or track who last fired
    s.save()
    return count

def toggle_streak_reaction(upload_id: int, user: User, r_type: str = 'fire'):
    try:
        upload = StreakUpload.objects.get(pk=upload_id)
        recipient = upload.user
        react = StreakReaction.objects.filter(streak_upload=upload, user=user, reaction_type=r_type).first()
        if react:
            react.delete()
            streak_count = update_streak_count(user, recipient)
            fire_count = StreakReaction.objects.filter(recipient=recipient, reaction_type='fire').count()
            return False, "Reaction removed", streak_count, fire_count
        else:
            StreakReaction.objects.create(streak_upload=upload, user=user, recipient=recipient, reaction_type=r_type)
            streak_count = update_streak_count(user, recipient)
            fire_count = StreakReaction.objects.filter(recipient=recipient, reaction_type='fire').count()
            
            # Notify recipient
            try:
                from ..notifications.services import create_notification
                sender_name = getattr(user.profile, 'display_name', user.username)
                create_notification(
                    recipient=recipient,
                    actor=user,
                    notification_type='streak_fire',
                    message=f"🔥 {sender_name} fired your streak upload!",
                    object_id=upload.id
                )
                tokens = _get_user_tokens(recipient.id)
                if tokens:
                    send_push_notification(
                        tokens,
                        title="🔥 New Fire!",
                        body=f"{sender_name} fired your streak upload!",
                        data={'type': 'streak_fire', 'upload_id': upload.id, 'user_id': user.id}
                    )
            except Exception:
                pass

            return True, "Reaction added", streak_count, fire_count
    except StreakUpload.DoesNotExist:
        return None, "Not found", 0, 0

def toggle_user_fire_service(recipient_id: int, user: User, r_type: str = 'fire'):
    try:
        recipient = User.objects.get(pk=recipient_id)
        # Toggle a reaction that isn't tied to a specific upload
        react = StreakReaction.objects.filter(streak_upload=None, user=user, recipient=recipient, reaction_type=r_type).first()
        if react:
            react.delete()
            streak_count = update_streak_count(user, recipient)
            fire_count = StreakReaction.objects.filter(recipient=recipient, reaction_type='fire').count()
            return False, "Reaction removed", streak_count, fire_count
        else:
            StreakReaction.objects.create(streak_upload=None, user=user, recipient=recipient, reaction_type=r_type)
            streak_count = update_streak_count(user, recipient)
            fire_count = StreakReaction.objects.filter(recipient=recipient, reaction_type='fire').count()
            
            # Notify recipient
            try:
                from ..notifications.services import create_notification
                sender_name = getattr(user.profile, 'display_name', user.username)
                create_notification(
                    recipient=recipient,
                    actor=user,
                    notification_type='user_fire',
                    message=f"🔥 {sender_name} sent you a fire!",
                    object_id=None
                )
                tokens = _get_user_tokens(recipient.id)
                if tokens:
                    send_push_notification(
                        tokens,
                        title="🔥 You've got fire!",
                        body=f"{sender_name} sent you a fire!",
                        data={'type': 'user_fire', 'user_id': user.id}
                    )
            except Exception:
                pass

            return True, "Reaction added", streak_count, fire_count
    except User.DoesNotExist:
        return None, "User not found", 0, 0

from datetime import timedelta
from django.db.models import Max

def get_streaks_list_service(user: User, view_type: str = 'friends', request=None):
    """
    Optimized: Get streaks list with minimal queries.
    """
    try:
        now = timezone.now()
        day_ago = now - timedelta(hours=24)
        
        if view_type == 'friends':
            # 1. Fetch streaks with optimized profile and uploader data
            streaks = Streak.objects.filter(
                models.Q(user1=user) | models.Q(user2=user),
                streak_count__gt=0
            ).select_related('user1__profile', 'user2__profile', 'last_uploader')
            
            # 2. Collect other users to batch fetch their latest uploads
            other_user_ids = []
            streak_map = {}
            for s in streaks:
                other_user = s.user2 if s.user1 == user else s.user1
                other_user_ids.append(other_user.id)
                streak_map[other_user.id] = s
            
            # 3. Batch fetch all uploads from 24h ago
            all_uploads = StreakUpload.objects.filter(
                user_id__in=other_user_ids,
                created_at__gte=day_ago
            ).order_by('created_at') # Order by oldest first
            
            # Group by user
            upload_groups = {}
            for up in all_uploads:
                if up.user_id not in upload_groups:
                    upload_groups[up.user_id] = []
                upload_groups[up.user_id].append(up)
            
            # 4. Include current user's own uploads if they exist
            my_uploads = StreakUpload.objects.filter(user=user, created_at__gte=day_ago).order_by('created_at')
            if my_uploads.exists():
                upload_groups[user.id] = list(my_uploads)
                if user.id not in other_user_ids:
                    other_user_ids.insert(0, user.id)
                    class MockStreak:
                        def __init__(self, u):
                            self.user1 = u
                            self.user2 = u
                            self.streak_count = 0
                            self.last_interaction_date = timezone.now()
                            self.last_uploader_id = u.id
                    streak_map[user.id] = MockStreak(user)
            
            result = []
            for uid in other_user_ids:
                s: Streak = streak_map[uid]
                other_user = s.user2 if s.user1 == user else s.user1
                ups = upload_groups.get(uid, [])
                
                # Format each media item
                media_list = []
                for up in ups:
                    has_liked = StreakLike.objects.filter(streak_upload=up, user=user).exists()
                    has_fired = StreakReaction.objects.filter(streak_upload=up, user=user, reaction_type='fire').exists()
                    media_list.append({
                        'id': up.id,
                        'media_url': get_absolute_media_url(up.media_url, request),
                        'media_type': up.media_type,
                        'likes_count': up.likes.count(),
                        'comments_count': up.comments.count(),
                        'has_liked': has_liked,
                        'has_fired': has_fired,
                        'created_at': up.created_at
                    })

                if not media_list:
                    continue

                result.append({
                    'user_id': other_user.id,
                    'username': other_user.username,
                    'display_name': getattr(other_user.profile, 'display_name', other_user.username),
                    'photo': ProfileSerializer(other_user.profile, context={'request': request}).data.get('photo'),
                    'streak_count': s.streak_count,
                    'last_updated': s.last_interaction_date,
                    'last_uploader_id': s.last_uploader_id,
                    'media_list': media_list,
                    'media': media_list[0] if media_list else None # Keep for backward compatibility (first as requested)
                })
            return result

        else: # type == 'all'
            # 1. Fetch latest public uploads OR the user's own uploads (portable)
            all_uploads = StreakUpload.objects.filter(
                models.Q(created_at__gte=day_ago) & (
                    models.Q(visibility='all') | models.Q(user=user)
                )
            ).select_related('user__profile').order_by('created_at') # Order by oldest first
            
            if not all_uploads.exists():
                return []
                
            # Group by user
            upload_groups = {}
            user_order = []
            for up in all_uploads:
                if up.user_id not in upload_groups:
                    upload_groups[up.user_id] = []
                    user_order.append(up.user_id)
                upload_groups[up.user_id].append(up)
            
            uploader_ids = user_order
            
            # 2. Bulk fetch the highest streak for each uploader
            from channels.db import database_sync_to_async # not needed here but for reference
            from django.db.models import Max, F
            from django.db.models.functions import Greatest
            
            user_streaks = User.objects.filter(id__in=uploader_ids).annotate(
                max_s1=Max('streaks_user1__streak_count'),
                max_s2=Max('streaks_user2__streak_count')
            ).annotate(
                best_streak=Greatest(F('max_s1'), F('max_s2'), default=0)
            )
            
            streak_data_map = {u.id: u.best_streak for u in user_streaks}
            
            result = []
            for uid in uploader_ids:
                ups = upload_groups[uid]
                first_up = ups[0]
                best_streak = streak_data_map.get(uid, 0)
                
                # Format each media item
                media_list = []
                for up in ups:
                    has_liked = StreakLike.objects.filter(streak_upload=up, user=user).exists()
                    has_fired = StreakReaction.objects.filter(streak_upload=up, user=user, reaction_type='fire').exists()
                    media_list.append({
                        'id': up.id,
                        'media_url': get_absolute_media_url(up.media_url, request),
                        'media_type': up.media_type,
                        'likes_count': up.likes.count(),
                        'comments_count': up.comments.count(),
                        'has_liked': has_liked,
                        'has_fired': has_fired,
                        'created_at': up.created_at
                    })
                
                result.append({
                    'user_id': first_up.user.id,
                    'username': first_up.user.username,
                    'display_name': getattr(first_up.user.profile, 'display_name', first_up.user.username),
                    'photo': ProfileSerializer(first_up.user.profile, context={'request': request}).data.get('photo'),
                    'streak_count': best_streak,
                    'last_updated': first_up.created_at,
                    'media_list': media_list,
                    'media': media_list[0] # Keep for backward compatibility (first as requested)
                })
            return result
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error in get_streaks_list_service: {e}")
        return []

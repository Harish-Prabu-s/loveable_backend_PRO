from ...models import Reel, ReelLike, ReelComment, User, Message
from ..chat.services import get_or_create_room

from django.db import models

def list_reels(user, limit: int = 10, page: int = 1, random_flag: bool = False, search: str = None):
    offset = (page - 1) * limit
    from django.db.models import Count, F
    
    qs = Reel.objects.select_related('user__profile').filter(
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

    qs = qs.annotate(
        lcount=Count('likes', distinct=True),
        ccount=Count('comments', distinct=True)
    ).annotate(
        popularity_score=(F('lcount') * 2) + (F('ccount') * 5)
    ).order_by('-popularity_score', '-created_at').distinct()[offset:offset+limit]
    
    qs = list(qs)
    
    if random_flag and page == 1:
        import random
        random.shuffle(qs)
        
    return qs

def create_reel(user, video_url: str, caption: str = '', visibility='all', mentions=None, audio_id=None, audio_meta=None, audio_start_sec=0, cover_image=None, editor_metadata=None, provider_track_id=None, provider_name='jiosaavn'):
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    from api.services.music_service import MusicService
    import uuid

    reel = Reel.objects.create(
        user=user, video_url=video_url, caption=caption, 
        visibility=visibility, audio_start_sec=int(audio_start_sec or 0),
        editor_metadata_json=editor_metadata or {}
    )
    
    if cover_image:
        filename = f"reels/covers/{user.id}_{uuid.uuid4().hex[:8]}_{getattr(cover_image, 'name', 'cover.jpg')}"
        path = default_storage.save(filename, ContentFile(cover_image.read() if hasattr(cover_image, 'read') else cover_image))
        reel.cover_image = path
        reel.save()

    # Handle Modern Music Integration
    if provider_track_id:
        track = MusicService.get_track(provider_track_id, provider_name)
        if track:
            reel.music_track = track
            reel.save(update_fields=['music_track'])
    
    # Handle Legacy Audio (only if no modern track)
    if not reel.music_track:
        if audio_id:
            try:
                from ...models import Audio
                audio = Audio.objects.filter(pk=audio_id).first()
                if audio:
                    reel.audio = audio
                    reel.save(update_fields=['audio'])
                    audio_id = audio.id
            except Exception:
                pass
        elif audio_meta and isinstance(audio_meta, dict):
            try:
                from ...models import Audio
                title = audio_meta.get('title', 'Original Audio')
                artist = audio_meta.get('artist', 'Unknown')
                cover_url = audio_meta.get('coverArt', '')
                ext_url = audio_meta.get('url', '')
                
                audio = Audio.objects.filter(title=title, artist=artist).first()
                created = False
                
                if not audio:
                    audio = Audio.objects.create(
                        title=title, artist=artist,
                        created_by=user, cover_image_url=cover_url
                    )
                    created = True
                
                if ext_url and (created or not audio.file_url or str(audio.file_url).startswith('http')):
                    audio.file_url = ext_url
                    audio.save(update_fields=['file_url'])

                reel.audio = audio
                reel.save(update_fields=['audio'])
                audio_id = audio.id
            except Exception as e:
                print(f"Error creating audio from meta: {e}")

    # Notify Close Friends, process mentions
    # ... (existing notification code)
    from ..notifications.services import notify_close_friends_of_content
    from ..notifications.utils import handle_mentions
    notify_close_friends_of_content(user, 'reel', reel.id)
    handle_mentions(caption, user, 'reel', reel.id, obj=reel, explicit_mentions=mentions)
    
    # Launch audio extraction if no existing audio attached
    if not audio_id and not reel.music_track:
        from .tasks import launch_audio_extraction
        launch_audio_extraction(reel.id)

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

def add_reel_comment(reel_id: int, user: User, text: str, reply_to_id: int = None):
    try:
        reel = Reel.objects.get(pk=reel_id)
        comment = ReelComment.objects.create(reel=reel, user=user, text=text, reply_to_id=reply_to_id)
        
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
        
        # Award coins for sharing (10 coins)
        try:
            from ...models import Wallet, CoinTransaction
            wallet, _ = Wallet.objects.get_or_create(user=sender)
            wallet.coin_balance += 10
            wallet.save(update_fields=['coin_balance', 'updated_at'])
            CoinTransaction.objects.create(
                wallet=wallet,
                amount=10,
                type='credit',
                transaction_type='earned',
                description=f"Reward for sharing Reel #{reel.id}"
            )
        except Exception as e:
            print(f"Error awarding coins for sharing reel: {e}")

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

def repost_reel(user, original_reel_id):
    """Create a repost of an existing reel if the user is mentioned.
    Returns (repost, error_code) tuple: error_code is None on success.
    """
    try:
        original = Reel.objects.get(id=original_reel_id)
    except Reel.DoesNotExist:
        return None, 'deleted'

    # Block if reel is archived
    if original.is_archived:
        return None, 'deleted'

    if not original.mentions.filter(id=user.id).exists() and original.user != user:
        return None, 'not_mentioned'

    repost = Reel.objects.create(
        user=user,
        video_url=original.video_url,
        caption=original.caption,
        visibility='all',
        reposted_from=original
    )
    return repost, None

def get_reel_by_id(pk: int):
    try:
        return Reel.objects.get(pk=pk)
    except Reel.DoesNotExist:
        return None

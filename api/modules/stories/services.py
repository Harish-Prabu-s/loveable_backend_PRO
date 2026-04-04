from django.utils import timezone
from datetime import timedelta
from ...models import Story, StoryView

def get_active_stories(user):
    """
    Returns stories that haven't expired (24h default) and are visible to the user.
    """
    now = timezone.now()
    from django.db import models
    return Story.objects.filter(
        models.Q(expires_at__gt=now) | models.Q(expires_at__isnull=True, created_at__gt=now - timedelta(hours=24))
    ).filter(
        models.Q(visibility='all') | 
        models.Q(user=user) | 
        (models.Q(visibility='close_friends') & models.Q(user__close_friends__close_friend=user))
    ).select_related('user__profile').prefetch_related('views').order_by('-created_at').distinct()

def create_story(user, media_url: str, media_type: str = 'image', visibility='all', caption: str = ''):
    expires_at = timezone.now() + timedelta(hours=24)
    story = Story.objects.create(
        user=user, 
        media_url=media_url, 
        media_type=media_type, 
        expires_at=expires_at, 
        visibility=visibility,
        caption=caption
    )
    
    # Notify Close Friends
    from ..notifications.services import notify_close_friends_of_content
    from ..notifications.utils import handle_mentions
    notify_close_friends_of_content(user, 'story', story.id)
    handle_mentions(caption, user, 'story', story.id, obj=story)
    
    return story

def add_story_comment(story_id: int, user, text: str):
    from ...models import StoryComment
    try:
        story = Story.objects.get(id=story_id)
        comment = StoryComment.objects.create(story=story, user=user, text=text)
        
        # Process Mentions
        from ..notifications.utils import handle_mentions
        handle_mentions(text, user, 'story_comment', story.id)
        
        return comment
    except Story.DoesNotExist:
        return None

def record_view(story_id: int, user):
    story = Story.objects.get(id=story_id)
    # Ignore if user views their own story
    if story.user == user:
        return None
    view, created = StoryView.objects.get_or_create(story=story, viewer=user)
    return view

def get_story_views(story_id: int):
    return StoryView.objects.filter(story_id=story_id).select_related('viewer__profile').order_by('-viewed_at')

def repost_story(user, original_story_id):
    """Create a repost of an existing story."""
    try:
        original = Story.objects.get(id=original_story_id)
        # Inherit media and caption, but set new owner and expires_at (24h from now)
        expires_at = timezone.now() + timedelta(hours=24)
        repost = Story.objects.create(
            user=user,
            media_url=original.media_url,
            media_type=original.media_type,
            caption=original.caption,
            expires_at=expires_at,
            visibility='all',
            reposted_from=original
        )
        return repost
    except Story.DoesNotExist:
        return None

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Post, PostLike, PostComment, Reel, ReelLike, ReelComment, Story, StoryLike, StoryComment, FollowRequest, FriendRequest, Message, Streak
from .modules.notifications.fcm_service import send_action_notification, notify_followers, notify_streak_update

logger = logging.getLogger(__name__)

# --- Uploads (Notify Followers) ---

@receiver(post_save, sender=Post)
def notify_post_upload(sender, instance, created, **kwargs):
    if created:
        notify_followers(instance.user.username, instance.user.id, 'post_upload', instance.id)

@receiver(post_save, sender=Reel)
def notify_reel_upload(sender, instance, created, **kwargs):
    if created:
        notify_followers(instance.user.username, instance.user.id, 'reel_upload', instance.id)

@receiver(post_save, sender=Story)
def notify_story_upload(sender, instance, created, **kwargs):
    if created:
        notify_followers(instance.user.username, instance.user.id, 'story_upload', instance.id)

# --- Social Likes & Comments ---

@receiver(post_save, sender=PostLike)
def notify_post_like(sender, instance, created, **kwargs):
    if created and instance.user != instance.post.user:
        send_action_notification(instance.user.username, instance.post.user.id, 'post_like', object_id=instance.post.id)

@receiver(post_save, sender=PostComment)
def notify_post_comment(sender, instance, created, **kwargs):
    if created and instance.user != instance.post.user:
        send_action_notification(instance.user.username, instance.post.user.id, 'post_comment', object_id=instance.post.id)

@receiver(post_save, sender=ReelLike)
def notify_reel_like(sender, instance, created, **kwargs):
    if created and instance.user != instance.reel.user:
        send_action_notification(instance.user.username, instance.reel.user.id, 'reel_like', object_id=instance.reel.id)

@receiver(post_save, sender=ReelComment)
def notify_reel_comment(sender, instance, created, **kwargs):
    if created and instance.user != instance.reel.user:
        send_action_notification(instance.user.username, instance.reel.user.id, 'reel_comment', object_id=instance.reel.id)

@receiver(post_save, sender=StoryLike)
def notify_story_like(sender, instance, created, **kwargs):
    if created and instance.user != instance.story.user:
        send_action_notification(instance.user.username, instance.story.user.id, 'story_like', object_id=instance.story.id)

# --- Friend Actions ---

@receiver(post_save, sender=FriendRequest)
def notify_friend_request(sender, instance, created, **kwargs):
    if created:
        send_action_notification(instance.from_user.username, instance.to_user.id, 'friend_request', object_id=instance.id)
    elif instance.status == 'accepted':
        send_action_notification(instance.to_user.username, instance.from_user.id, 'friend_request_accepted', object_id=instance.to_user.id)

# --- Messages & Streaks ---

@receiver(post_save, sender=Message)
def notify_new_message(sender, instance, created, **kwargs):
    if created:
        actor = instance.sender
        room = instance.room
        recipient = room.receiver if room.caller == actor else room.caller
        if room.status == 'active': return
        send_action_notification(actor.username, recipient.id, 'chat_message', object_id=room.id, extra_data={'body': instance.content[:50]})

@receiver(post_save, sender=Streak)
def notify_streak_milestone(sender, instance, created, **kwargs):
    # Only notify on specific milestones or if it's a "big" increment (e.g., every 5 days or first day)
    if instance.streak_count > 0 and (instance.streak_count == 1 or instance.streak_count % 5 == 0):
        notify_streak_update(instance.user1_id, instance.user2_id, instance.streak_count)

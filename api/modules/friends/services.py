from django.contrib.auth.models import User
from django.db import models
from ...models import FriendRequest, Follow, Notification
from ..notifications.push_service import send_push_notification, _get_user_tokens

def send_friend_request(user: User, target_user_id: int):
    if user.id == int(target_user_id):
        return None, "Cannot friend yourself"
    try:
        target = User.objects.get(id=target_user_id)
        existing = FriendRequest.objects.filter(
            (models.Q(from_user=user, to_user=target) | models.Q(from_user=target, to_user=user))
        ).first()

        if existing:
            if existing.status == 'accepted':
                return existing, "Already friends"
            if existing.status == 'pending':
                return existing, "Request already pending"
            return existing, "Request exists"

        req = FriendRequest.objects.create(from_user=user, to_user=target, status='pending')

        # Send Notifications
        profile = getattr(user, 'profile', None)
        sender_name = profile.display_name if profile else user.username
        
        Notification.objects.create(
            recipient=target,
            actor=user,
            notification_type='friend_request',
            message=f"You received a friend request from {sender_name}",
            object_id=req.id
        )

        tokens = _get_user_tokens(target.id)
        if tokens:
            send_push_notification(
                tokens,
                title="New Friend Request",
                body=f"You received a friend request from {sender_name}",
                data={'type': 'friend_request', 'user_id': user.id}
            )

        return req, "Request sent"
    except User.DoesNotExist:
        return None, "User not found"

def accept_friend_request(user: User, from_user_id: int):
    try:
        from_user = User.objects.get(id=from_user_id)
        req = FriendRequest.objects.filter(from_user=from_user, to_user=user, status='pending').first()
        if not req:
            return None, "No pending request found"

        req.status = 'accepted'
        req.save()

        Follow.objects.get_or_create(follower=req.from_user, following=req.to_user)
        Follow.objects.get_or_create(follower=req.to_user, following=req.from_user)

        # Notify acceptance
        profile = getattr(user, 'profile', None)
        acceptor_name = profile.display_name if profile else user.username

        Notification.objects.create(
            recipient=from_user,
            actor=user,
            notification_type='friend_accept',
            message=f"{acceptor_name} accepted your friend request",
            object_id=req.id
        )

        tokens = _get_user_tokens(from_user.id)
        if tokens:
            send_push_notification(
                tokens,
                title="Friend Request Accepted",
                body=f"{acceptor_name} accepted your friend request",
                data={'type': 'friend_accept', 'user_id': user.id}
            )

        return req, "Request accepted"
    except User.DoesNotExist:
        return None, "User not found"

def reject_friend_request(user: User, from_user_id: int):
    try:
        from_user = User.objects.get(id=from_user_id)
        req = FriendRequest.objects.filter(from_user=from_user, to_user=user, status='pending').first()
        if not req:
            return None, "No pending request found"

        req.status = 'rejected'
        req.save()

        return req, "Request rejected"
    except User.DoesNotExist:
        return None, "User not found"

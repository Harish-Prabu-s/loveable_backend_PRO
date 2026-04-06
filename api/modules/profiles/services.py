from django.contrib.auth.models import User
from django.db import models
from ...models import Profile, Follow, FriendRequest

def get_my_profile(user: User) -> Profile:
    return user.profile

def update_my_profile(user, data, files=None):
    p = get_my_profile(user)
    
    # Handle username update (on the User model)
    if 'username' in data:
        new_username = data['username'].strip()
        if new_username and new_username != user.username:
            # Check for uniqueness
            if not User.objects.filter(username=new_username).exists():
                user.username = new_username
                user.save()
    
    if 'display_name' in data:
        p.display_name = data['display_name']
    if 'bio' in data:
        p.bio = data['bio']
    if 'gender' in data:
        p.gender = data['gender']
        
    if files and 'photo' in files:
        p.photo = files['photo']
    elif 'photo' in data and not isinstance(data['photo'], str): # sometimes arrives in data
        p.photo = data['photo']
    elif 'photo' in data and not data['photo']: # Allow clearing the photo
        p.photo = None

    p.save()
    return p

def follow_user(user: User, target_user_id: int):
    """Follow a user and notify them."""
    if user.id == target_user_id:
        return None
    try:
        from ..notifications.services import create_notification
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        
        target = User.objects.get(id=target_user_id)
        follow, created = Follow.objects.get_or_create(follower=user, following=target)
        
        if created:
            profile = getattr(user, 'profile', None)
            sender_name = profile.display_name if profile else user.username
            create_notification(recipient=target, actor=user, notification_type='follow', message=f"{sender_name} started following you!")
            tokens = _get_user_tokens(target_user_id)
            if tokens:
                send_push_notification(tokens, title="New Follower!", body=f"{sender_name} started following you!", data={'type': 'follow', 'user_id': user.id})
        return follow
    except User.DoesNotExist:
        return None

def unfollow_user(user: User, target_user_id: int):
    """Unfollow a user."""
    Follow.objects.filter(follower=user, following_id=target_user_id).delete()

def send_friend_request(user: User, target_user_id: int):
    """Send a friend request and notify the target user."""
    if user.id == target_user_id:
        return None, "Cannot friend yourself"
    try:
        from ..notifications.services import create_notification
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        
        target = User.objects.get(id=target_user_id)
        existing = FriendRequest.objects.filter((models.Q(from_user=user, to_user=target) | models.Q(from_user=target, to_user=user))).first()
        
        if existing:
            if existing.status == 'accepted': return existing, "Already friends"
            if existing.status == 'pending': return existing, "Request already pending"
            return existing, "Request exists"

        req = FriendRequest.objects.create(from_user=user, to_user=target, status='pending')
        
        # Notify
        profile = getattr(user, 'profile', None)
        sender_name = profile.display_name if profile else user.username
        create_notification(recipient=target, actor=user, notification_type='friend_request', message=f"{sender_name} sent you a friend request", object_id=req.id)
        tokens = _get_user_tokens(target_user_id)
        if tokens:
            send_push_notification(tokens, title="Friend Request", body=f"{sender_name} sent you a friend request!", data={'type': 'friend_request', 'request_id': req.id})
            
        return req, "Request sent"
    except User.DoesNotExist:
        return None, "User not found"

def respond_friend_request(user: User, request_id: int, action: str):
    # action: 'accept' or 'reject'
    try:
        req = FriendRequest.objects.get(id=request_id, to_user=user)
        
        # If it's already in the target state, just return it (idempotency)
        if req.status == action + 'ed':
            return req
            
        # If it's already processed but into a DIFFERENT state (e.g. was rejected, now trying to accept)
        # We only allow responding to 'pending' requests.
        if req.status != 'pending':
            return None

        if action == 'accept':
            req.status = 'accepted'
            req.save()
            # Auto-follow each other
            Follow.objects.get_or_create(follower=req.from_user, following=req.to_user)
            Follow.objects.get_or_create(follower=req.to_user, following=req.from_user)
            
            # Notify the sender that their request was accepted
            from ..notifications.services import create_notification
            from ..notifications.push_service import send_push_notification, _get_user_tokens
            
            profile = getattr(user, 'profile', None)
            sender_name = profile.display_name if profile else user.username
            
            create_notification(
                recipient=req.from_user,
                actor=user,
                notification_type='friend_accepted',
                message=f"{sender_name} accepted your friend request!",
                object_id=req.id
            )
            
            tokens = _get_user_tokens(req.from_user.id)
            if tokens:
                send_push_notification(
                    tokens,
                    title="Friend Request Accepted!",
                    body=f"{sender_name} accepted your friend request!",
                    data={'type': 'friend_accepted', 'user_id': user.id}
                )
        elif action == 'reject':
            req.status = 'rejected'
            req.save()
        return req
    except FriendRequest.DoesNotExist:
        return None

def share_profile_to_chat(sender: User, shared_user_id: int, target_user_id: int):
    try:
        shared_user = User.objects.get(pk=shared_user_id)
        target_user = User.objects.get(pk=target_user_id)
        
        # Deduct 10 coins
        from ...models import Wallet, CoinTransaction
        wallet, _ = Wallet.objects.get_or_create(user=sender)
        if wallet.coin_balance < 10:
            return {'error': 'Insufficient coins (10 required).', 'status': 400}
            
        wallet.coin_balance -= 10
        wallet.save(update_fields=['coin_balance', 'updated_at'])
        
        CoinTransaction.objects.create(
            wallet=wallet,
            amount=10,
            type='debit',
            transaction_type='spent',
            description=f"Shared user #{shared_user.id}'s profile"
        )
        
        from ..chat.services import get_or_create_room
        from ...models import Message
        room = get_or_create_room(sender, target_user.id, 'audio')
        
        message = Message.objects.create(
            room=room,
            sender=sender,
            content=f"[PROFILE_SHARE:{shared_user.id}]",
            type='profile_share'
        )
        
        # Notify
        from ..notifications.services import create_notification
        from ..notifications.push_service import send_push_notification, _get_user_tokens
        profile = getattr(sender, 'profile', None)
        sender_name = profile.display_name if profile else sender.username
        create_notification(recipient=target_user, actor=sender, notification_type='profile_share', message=f"{sender_name} shared a profile with you.")
        tokens = _get_user_tokens(target_user.id)
        if tokens:
            send_push_notification(tokens, title="Shared Profile", body=f"{sender_name} shared a profile with you.", data={'type': 'profile_share'})
            
        return {'success': True}
    except User.DoesNotExist:
        return {'error': 'User not found', 'status': 404}

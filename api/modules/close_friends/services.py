from django.contrib.auth.models import User
from ...models import CloseFriend, Notification
from ...serializers import ProfileSerializer

def add_close_friend_service(user: User, target_user_id: int):
    if user.id == int(target_user_id):
        return None, "Cannot add yourself as close friend"
    try:
        target = User.objects.get(id=target_user_id)
        
        # Check if already close friend
        if CloseFriend.objects.filter(user=user, close_friend=target).exists():
            return None, "Already in close friends"
            
        cf = CloseFriend.objects.create(user=user, close_friend=target)
        
        # Optional: Send a notification, but usually you don't notify when you add someone to close friends.
        return cf, "Added to close friends"
    except User.DoesNotExist:
        return None, "User not found"

def remove_close_friend_service(user: User, target_user_id: int):
    try:
        target = User.objects.get(id=target_user_id)
        cf = CloseFriend.objects.filter(user=user, close_friend=target).first()
        if not cf:
            return False, "Not in close friends"
        cf.delete()
        return True, "Removed from close friends"
    except User.DoesNotExist:
        return False, "User not found"

def list_close_friends_service(user: User, request=None):
    from ...serializers import CloseFriendSerializer
    close_friends = CloseFriend.objects.filter(user=user).select_related('close_friend__profile')
    return CloseFriendSerializer(close_friends, many=True, context={'request': request}).data

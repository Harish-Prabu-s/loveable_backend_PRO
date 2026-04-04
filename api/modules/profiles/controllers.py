from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ...serializers import ProfileSerializer
from .services import get_my_profile, update_my_profile, follow_user, unfollow_user, send_friend_request, respond_friend_request
from ...models import Profile

@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def profile_me(request):
    if request.method == 'GET':
        p = get_my_profile(request.user)
        return Response(ProfileSerializer(p, context={'request': request}).data)
    if request.method == 'PATCH':
        p = update_my_profile(request.user, request.data, request.FILES)
        return Response(ProfileSerializer(p, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_profiles_view(request):
    search = request.GET.get('search')
    is_online = request.GET.get('is_online')
    is_busy = request.GET.get('is_busy')
    relationship = request.GET.get('relationship') # 'friends' for mentions
    
    # Base queryset: exclude self
    qs = Profile.objects.exclude(user=request.user).select_related('user')
    
    if relationship == 'friends':
        from ...models import Follow, FriendRequest
        # Get IDs of people the user follows or who follow the user
        following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
        follower_ids = Follow.objects.filter(following=request.user).values_list('follower_id', flat=True)
        # Get IDs of accepted friends
        friend_ids = FriendRequest.objects.filter(
            (models.Q(from_user=request.user) | models.Q(to_user=request.user)),
            status='accepted'
        ).values_list('from_user_id', 'to_user_id')
        
        # Flatten friend IDs
        flat_friend_ids = set()
        for f in friend_ids:
            flat_friend_ids.add(f[0])
            flat_friend_ids.add(f[1])
        
        # Combined social circle
        social_ids = set(following_ids) | set(follower_ids) | flat_friend_ids
        if request.user.id in social_ids:
            social_ids.remove(request.user.id)
            
        qs = qs.filter(user_id__in=social_ids)

    if search:
        from django.db.models import Q
        qs = qs.filter(Q(display_name__icontains=search) | Q(username__icontains=search))
    
    if is_online == 'true':
        qs = qs.filter(is_online=True)
        
    if is_busy == 'false':
        # Efficiency hint: for millions of users, this should be a cached 'is_busy' flag on the Profile model itself
        # to avoid joining with the Room table every time.
        qs = qs.exclude(user__rooms_started__status__in=['pending', 'active'])
        qs = qs.exclude(user__rooms_received__status__in=['pending', 'active'])
        
    return Response(ProfileSerializer(qs, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile_by_id(request, user_id: int):
    p = Profile.objects.filter(user_id=user_id).first()
    if not p:
        return Response({'error': 'not found'}, status=404)
    return Response(ProfileSerializer(p, context={'request': request}).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def follow_view(request, user_id: int):
    follow_user(request.user, user_id)
    return Response({'status': 'followed'})
    
    return Response({'status': 'followed'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unfollow_view(request, user_id: int):
    unfollow_user(request.user, user_id)
    return Response({'status': 'unfollowed'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_friend_request_view(request, user_id: int):
    req, msg = send_friend_request(request.user, user_id)
    if not req:
        return Response({'error': msg}, status=400)
    return Response({'status': msg, 'request_id': req.id})
        
    return Response({'status': msg, 'request_id': req.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def respond_friend_request_view(request, request_id: int):
    action = request.data.get('action') # accept/reject
    if action not in ['accept', 'reject']:
        return Response({'error': 'Invalid action'}, status=400)
    
    req = respond_friend_request(request.user, request_id, action)
    if not req:
        return Response({'error': 'Request not found or invalid'}, status=404)
    return Response({'status': f'Request {action}ed'})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_followers_view(request, user_id: int):
    # Returns list of profiles that follow this user
    from ...models import Follow, Profile
    # Get IDs of all people who follow this user
    follower_ids = Follow.objects.filter(following_id=user_id).values_list('follower_id', flat=True)
    # Fetch profiles of those users
    profiles = Profile.objects.filter(user_id__in=follower_ids).select_related('user')
    return Response(ProfileSerializer(profiles, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_following_view(request, user_id: int):
    # Returns list of profiles this user follows
    from ...models import Follow, Profile
    # Get IDs of all people this user follows
    following_ids = Follow.objects.filter(follower_id=user_id).values_list('following_id', flat=True)
    # Fetch profiles of those users
    profiles = Profile.objects.filter(user_id__in=following_ids).select_related('user')
    return Response(ProfileSerializer(profiles, many=True, context={'request': request}).data)

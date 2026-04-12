from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
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
def profile_insights_view(request):
    """
    Real analytics for the authenticated user's profile:
    - Total & per-day post/reel views (last 7 days)
    - Total likes/comments across posts, reels and stories
    - Follower growth vs prior week
    - Engagement rate = (total_likes + total_comments) / total_content * 100
    """
    from django.db.models import Count
    from django.utils import timezone
    from datetime import timedelta
    from ...models import (
        Post, Reel, Story,
        PostLike, PostComment, PostView,
        ReelLike, ReelComment, ReelView,
        StoryLike, StoryView,
        Follow,
    )

    user = request.user
    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # ── Content sets owned by this user ──────────────────────────────────────
    user_posts = Post.objects.filter(user=user, is_archived=False)
    user_reels = Reel.objects.filter(user=user, is_archived=False)
    user_stories = Story.objects.filter(user=user)

    post_ids = list(user_posts.values_list('id', flat=True))
    reel_ids = list(user_reels.values_list('id', flat=True))
    story_ids = list(user_stories.values_list('id', flat=True))

    # ── Overall totals ────────────────────────────────────────────────────────
    total_likes = (
        PostLike.objects.filter(post_id__in=post_ids).count()
        + ReelLike.objects.filter(reel_id__in=reel_ids).count()
        + StoryLike.objects.filter(story_id__in=story_ids).count()
    )
    total_comments = (
        PostComment.objects.filter(post_id__in=post_ids).count()
        + ReelComment.objects.filter(reel_id__in=reel_ids).count()
    )
    total_shares = 0  # Placeholder; add a Share model later if needed

    total_views = (
        PostView.objects.filter(post_id__in=post_ids).count()
        + ReelView.objects.filter(reel_id__in=reel_ids).count()
        + StoryView.objects.filter(story_id__in=story_ids).count()
    )

    total_content = len(post_ids) + len(reel_ids) + len(story_ids)
    if total_content > 0:
        engagement_rate = round((total_likes + total_comments) / max(total_views, 1) * 100, 1)
    else:
        engagement_rate = 0.0

    # ── Per-day views for the last 7 days ────────────────────────────────────
    DAY_ABBR = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    daily_views = {d: 0 for d in range(7)}  # key = 0 (Mon) … 6 (Sun)

    # Collect viewed_at grouped by weekday for each view type
    for qs, date_field, id_field, id_list in [
        (PostView.objects, 'viewed_at', 'post_id', post_ids),
        (ReelView.objects, 'viewed_at', 'reel_id', reel_ids),
        (StoryView.objects, 'viewed_at', 'story_id', story_ids),
    ]:
        rows = qs.filter(**{
            f"{id_field}__in": id_list,
            f"{date_field}__gte": week_ago,
        }).values_list(date_field, flat=True)
        for dt in rows:
            daily_views[dt.weekday()] += 1

    profile_views_week = [
        {"day": DAY_ABBR[i], "count": daily_views[i]}
        for i in range(7)
    ]

    # ── Follower growth (this week vs last week) ──────────────────────────────
    followers_now = Follow.objects.filter(following=user, created_at__gte=week_ago).count()
    followers_prev = Follow.objects.filter(
        following=user,
        created_at__gte=two_weeks_ago,
        created_at__lt=week_ago,
    ).count()
    followers_growth = followers_now - followers_prev
    followers_total = Follow.objects.filter(following=user).count()
    followers_growth_pct = (
        round(followers_growth / followers_prev * 100, 1)
        if followers_prev > 0
        else (100.0 if followers_growth > 0 else 0.0)
    )

    return Response({
        "profile_views_total": total_views,
        "profile_views_week": profile_views_week,
        "engagement_rate": engagement_rate,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "total_shares": total_shares,
        "followers_total": followers_total,
        "followers_growth": followers_growth,
        "followers_growth_pct": followers_growth_pct,
    })

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def suggestion_profiles_view(request):
    from ...models import Follow, FriendRequest
    user = request.user
    
    # Exclude self
    qs = Profile.objects.exclude(user=user).select_related('user')
    
    # Exclude already following
    following_ids = Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    
    # Exclude friends
    friend_ids = FriendRequest.objects.filter(
        (Q(from_user=user) | Q(to_user=user)),
        status='accepted'
    ).values_list('from_user_id', 'to_user_id')
    
    flat_friend_ids = set()
    for f in friend_ids:
        flat_friend_ids.add(f[0])
        flat_friend_ids.add(f[1])
        
    exclude_ids = set(following_ids) | flat_friend_ids
    if exclude_ids:
        qs = qs.exclude(user_id__in=exclude_ids)
        
    # Return up to 10 random suggestions
    suggestions = qs.order_by('?')[:10]
    return Response(ProfileSerializer(suggestions, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_profiles_view(request):
    search = request.GET.get('search')
    is_online = request.GET.get('is_online')
    is_busy = request.GET.get('is_busy')
    relationship = request.GET.get('relationship') # 'friends' for mentions
    new_users = request.GET.get('new_users')
    
    # Base queryset: exclude self
    qs = Profile.objects.exclude(user=request.user).select_related('user')
    
    if relationship == 'friends':
        from ...models import Follow, FriendRequest
        # Get IDs of people the user follows or who follow the user
        following_ids = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
        follower_ids = Follow.objects.filter(following=request.user).values_list('follower_id', flat=True)
        # Get IDs of accepted friends
        friend_ids = FriendRequest.objects.filter(
            (Q(from_user=request.user) | Q(to_user=request.user)),
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
        qs = qs.filter(Q(display_name__icontains=search) | Q(user__username__icontains=search))
    
    if is_online == 'true':
        qs = qs.filter(is_online=True)
        
    if is_busy == 'false':
        # Efficiency hint: for millions of users, this should be a cached 'is_busy' flag on the Profile model itself
        # to avoid joining with the Room table every time.
        qs = qs.exclude(user__rooms_started__status__in=['pending', 'active'])
        qs = qs.exclude(user__rooms_received__status__in=['pending', 'active'])
        
    if new_users == 'true':
        qs = qs.order_by('-user__date_joined')
        
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def share_profile_view(request, user_id: int):
    from .services import share_profile_to_chat
    target_user_id = request.data.get('target_user_id')
    if not target_user_id:
        return Response({'error': 'target_user_id required'}, status=400)
    
    result = share_profile_to_chat(request.user, user_id, target_user_id)
    if 'error' in result:
        return Response({'error': result['error']}, status=result['status'])
    return Response({'success': True})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mutual_connections_view(request, user_id: int):
    from ...models import Follow, Profile
    # People the target user follows
    target_following = Follow.objects.filter(follower_id=user_id).values_list('following_id', flat=True)
    # People the request user follows
    my_following = Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    
    # Mutual ids
    mutual_ids = set(target_following).intersection(set(my_following))
    
    profiles = Profile.objects.filter(user_id__in=mutual_ids).select_related('user')
    data = ProfileSerializer(profiles, many=True, context={'request': request}).data
    return Response({"count": len(mutual_ids), "results": data})

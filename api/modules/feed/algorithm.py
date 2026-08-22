"""
Smart Feed Algorithm
====================
Personalizes the post/reel feed for each user based on their recent behaviour.

Scoring formula applied to each candidate item:
  final_score = (base_engagement × 0.40)
              + (hashtag_match   × 0.30)
              + (creator_follow  × 0.20)
              + (recency_bonus   × 0.10)

User Interest Profile (last 30 days):
  - Hashtags the user has liked/viewed/commented on
  - Creator IDs the user follows
  - Content type preference (post vs reel ratio)
"""

from datetime import timedelta
from django.utils import timezone
from django.db.models import Q


# ── Constants ─────────────────────────────────────────────────────────────────
INTEREST_WINDOW_DAYS = 30     # How far back to look at user behaviour
MAX_ENGAGEMENT_NORM  = 1000.0 # Normalise raw engagement scores (0–1 scale)
RECENCY_HALF_LIFE_H  = 48     # Content older than 48h decays by ~50%


def _get_user_interest_profile(user):
    """
    Returns a dict describing what this user has recently engaged with.
    {
        'hashtag_ids': set of hashtag IDs user interacted with,
        'followed_ids': set of user IDs this user follows,
        'liked_post_ids': set,
        'liked_reel_ids': set,
    }
    """
    from api.models import PostLike, ReelLike, PostView, ReelView, Follow, PostComment, ReelComment

    cutoff = timezone.now() - timedelta(days=INTEREST_WINDOW_DAYS)

    # Posts the user liked/viewed/commented on recently
    liked_posts  = PostLike.objects.filter(user=user, created_at__gte=cutoff).values_list('post_id', flat=True)
    viewed_posts = PostView.objects.filter(viewer=user, viewed_at__gte=cutoff).values_list('post_id', flat=True)
    commented_posts = PostComment.objects.filter(user=user, created_at__gte=cutoff).values_list('post_id', flat=True)

    liked_reels  = ReelLike.objects.filter(user=user, created_at__gte=cutoff).values_list('reel_id', flat=True)
    viewed_reels = ReelView.objects.filter(viewer=user, viewed_at__gte=cutoff).values_list('reel_id', flat=True)
    commented_reels = ReelComment.objects.filter(user=user, created_at__gte=cutoff).values_list('reel_id', flat=True)

    # Collect all post/reel IDs user engaged with
    from api.models import Post, Reel
    engaged_post_ids = set(liked_posts) | set(viewed_posts) | set(commented_posts)
    engaged_reel_ids = set(liked_reels) | set(viewed_reels) | set(commented_reels)

    # Extract hashtags from those engaged posts/reels
    hashtag_ids = set()
    if engaged_post_ids:
        hashtag_ids |= set(
            Post.objects.filter(id__in=engaged_post_ids)
                .values_list('hashtags__id', flat=True)
        ) - {None}
    if engaged_reel_ids:
        hashtag_ids |= set(
            Reel.objects.filter(id__in=engaged_reel_ids)
                .values_list('hashtags__id', flat=True)
        ) - {None}

    # People the user follows
    followed_ids = set(
        Follow.objects.filter(follower=user).values_list('following_id', flat=True)
    )

    return {
        'hashtag_ids':    hashtag_ids,
        'followed_ids':   followed_ids,
        'liked_post_ids': set(liked_posts),
        'liked_reel_ids': set(liked_reels),
    }


def _recency_score(created_at) -> float:
    """
    Returns a 0–1 score that decays as content gets older.
    Content posted now → 1.0; content RECENCY_HALF_LIFE_H hours old → ~0.5.
    """
    import math
    age_hours = (timezone.now() - created_at).total_seconds() / 3600
    return math.exp(-0.693 * age_hours / RECENCY_HALF_LIFE_H)  # 0.693 = ln(2)


def _score_post(post, profile: dict) -> float:
    norm_engagement = min(post.engagement_score / MAX_ENGAGEMENT_NORM, 1.0)

    # Hashtag match boost
    post_hashtag_ids = set(post.hashtags.values_list('id', flat=True))
    hashtag_overlap  = len(post_hashtag_ids & profile['hashtag_ids'])
    hashtag_boost    = min(hashtag_overlap / max(len(post_hashtag_ids), 1), 1.0) if post_hashtag_ids else 0.0

    creator_boost = 1.0 if post.user_id in profile['followed_ids'] else 0.0
    recency       = _recency_score(post.created_at)

    return (norm_engagement * 0.40) + (hashtag_boost * 0.30) + (creator_boost * 0.20) + (recency * 0.10)


def _score_reel(reel, profile: dict) -> float:
    norm_engagement = min(reel.engagement_score / MAX_ENGAGEMENT_NORM, 1.0)

    reel_hashtag_ids = set(reel.hashtags.values_list('id', flat=True))
    hashtag_overlap  = len(reel_hashtag_ids & profile['hashtag_ids'])
    hashtag_boost    = min(hashtag_overlap / max(len(reel_hashtag_ids), 1), 1.0) if reel_hashtag_ids else 0.0

    creator_boost = 1.0 if reel.user_id in profile['followed_ids'] else 0.0
    recency       = _recency_score(reel.created_at)

    return (norm_engagement * 0.40) + (hashtag_boost * 0.30) + (creator_boost * 0.20) + (recency * 0.10)


def get_personalized_feed(user, limit: int = 20, page: int = 1, content_type: str = 'mixed'):
    """
    Returns a sorted list of dicts:
        {'type': 'post'|'reel', 'id': int, 'score': float, 'obj': Post|Reel}

    content_type: 'mixed' | 'posts' | 'reels'
    """
    from api.models import Post, Reel

    profile = _get_user_interest_profile(user)
    visibility_q = Q(visibility='all') | Q(user=user) | (
        Q(visibility='close_friends') & Q(user__close_friends__close_friend=user)
    )

    candidates = []

    if content_type in ('mixed', 'posts'):
        posts = (
            Post.objects
            .select_related('user__profile')
            .prefetch_related('hashtags', 'likes')
            .filter(is_archived=False)
            .filter(visibility_q)
            .exclude(id__in=profile['liked_post_ids'])  # Don't re-show already liked
            .order_by('-engagement_score', '-created_at')
            [:limit * 3]  # Fetch wider pool to score then trim
        )
        for p in posts:
            candidates.append({
                'type':  'post',
                'id':    p.id,
                'score': _score_post(p, profile),
                'obj':   p,
            })

    if content_type in ('mixed', 'reels'):
        reels = (
            Reel.objects
            .select_related('user__profile')
            .prefetch_related('hashtags', 'likes')
            .filter(is_archived=False)
            .filter(visibility_q)
            .exclude(id__in=profile['liked_reel_ids'])
            .order_by('-engagement_score', '-created_at')
            [:limit * 3]
        )
        for r in reels:
            candidates.append({
                'type':  'reel',
                'id':    r.id,
                'score': _score_reel(r, profile),
                'obj':   r,
            })

    # Sort all candidates by personalized score (descending)
    candidates.sort(key=lambda x: x['score'], reverse=True)

    # Paginate
    offset = (page - 1) * limit
    return candidates[offset: offset + limit]

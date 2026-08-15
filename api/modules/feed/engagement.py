"""
Engagement Score Engine
=======================
Recalculates and caches the engagement_score field on Post and Reel.

Score formula (weights chosen to reflect real recommendation value):
  likes   × 3   — explicit positive signal
  views   × 1   — passive interest
  comments × 5  — high-intent interaction
  shares  × 8   — strongest signal (user vouches for the content)

Scores are updated in-place via update_fields for minimal DB load.
"""

from django.db.models import Count


def recalculate_post_score(post) -> float:
    """
    Recalculate and save engagement_score for a Post instance.
    Returns the new score.
    """
    likes    = post.likes.count()
    comments = post.comments.count()
    views    = post.view_count    # already cached counter
    shares   = post.share_count   # already cached counter

    score = (likes * 3) + (views * 1) + (comments * 5) + (shares * 8)
    post.engagement_score = float(score)
    post.save(update_fields=['engagement_score'])
    return score


def recalculate_reel_score(reel) -> float:
    """
    Recalculate and save engagement_score for a Reel instance.
    Returns the new score.
    """
    likes    = reel.likes.count()
    comments = reel.comments.count()
    views    = reel.view_count
    shares   = reel.share_count

    score = (likes * 3) + (views * 1) + (comments * 5) + (shares * 8)
    reel.engagement_score = float(score)
    reel.save(update_fields=['engagement_score'])
    return score


def increment_post_view(post_id: int) -> None:
    """Atomically increment view_count and recalculate score for a Post."""
    from api.models import Post
    from django.db.models import F
    Post.objects.filter(pk=post_id).update(view_count=F('view_count') + 1)
    try:
        post = Post.objects.get(pk=post_id)
        recalculate_post_score(post)
    except Post.DoesNotExist:
        pass


def increment_reel_view(reel_id: int) -> None:
    """Atomically increment view_count and recalculate score for a Reel."""
    from api.models import Reel
    from django.db.models import F
    Reel.objects.filter(pk=reel_id).update(view_count=F('view_count') + 1)
    try:
        reel = Reel.objects.get(pk=reel_id)
        recalculate_reel_score(reel)
    except Reel.DoesNotExist:
        pass


def increment_post_share(post_id: int) -> None:
    """Atomically increment share_count and recalculate score for a Post."""
    from api.models import Post
    from django.db.models import F
    Post.objects.filter(pk=post_id).update(share_count=F('share_count') + 1)
    try:
        post = Post.objects.get(pk=post_id)
        recalculate_post_score(post)
    except Post.DoesNotExist:
        pass


def increment_reel_share(reel_id: int) -> None:
    """Atomically increment share_count and recalculate score for a Reel."""
    from api.models import Reel
    from django.db.models import F
    Reel.objects.filter(pk=reel_id).update(share_count=F('share_count') + 1)
    try:
        reel = Reel.objects.get(pk=reel_id)
        recalculate_reel_score(reel)
    except Reel.DoesNotExist:
        pass

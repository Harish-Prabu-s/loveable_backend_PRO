"""
ContentScore Model
==================
Stores pre-computed ranking scores for each piece of content.

Updated hourly by the Celery Beat task `compute_popularity_and_cf`.
Read by the feed builder task to assemble per-user feeds.

This table is the bridge between the raw event log and the served feed —
it converts noisy event data into clean, queryable scores.
"""

from django.db import models


class ContentScore(models.Model):
    """
    Pre-computed ranking scores for a single content item.

    Fields:
    - content_id: FK-like reference to the Reel/Post (PositiveBigIntegerField
      rather than FK so ranking works across content types without joins).
    - popularity_score: recency-decayed global engagement score.
    - cf_score: collaborative filtering score (avg of item-item similarities).
    - combined_score: weighted blend of popularity + CF (pre-computed for
      fast reads in the feed builder).
    """

    content_id = models.PositiveBigIntegerField(
        db_index=True,
        help_text='ID of the Reel or Post this score refers to.',
    )
    content_type = models.CharField(
        max_length=10, default='reel',
        choices=(('reel', 'Reel'), ('post', 'Post')),
        help_text='Type of content for disambiguation.',
    )
    popularity_score = models.FloatField(default=0.0)
    cf_score = models.FloatField(default=0.0)
    combined_score = models.FloatField(
        default=0.0, db_index=True,
        help_text='Weighted blend: 0.6 * popularity + 0.4 * cf. Pre-computed.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('content_type', 'content_id')
        indexes = [
            models.Index(fields=['-combined_score'], name='idx_cscore_combined_desc'),
        ]
        ordering = ['-combined_score']

    def __str__(self):
        return (
            f'ContentScore({self.content_type}:{self.content_id}) '
            f'pop={self.popularity_score:.2f} cf={self.cf_score:.2f} '
            f'combined={self.combined_score:.2f}'
        )

class CreatorScore(models.Model):
    """
    Pre-computed quality scores for creators, aggregated from all their content.
    Used as the 'creator affinity' (C) term in the ranking formula.
    """
    creator_id = models.PositiveBigIntegerField(unique=True, db_index=True)
    
    # Raw metrics
    avg_completion_rate = models.FloatField(default=0.0)
    share_rate = models.FloatField(default=0.0)
    save_rate = models.FloatField(default=0.0)
    report_rate = models.FloatField(default=0.0)
    upload_count_30d = models.IntegerField(default=0)
    
    # Final aggregated score (higher is better)
    quality_score = models.FloatField(default=0.0, db_index=True)
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'CreatorScore(creator_id={self.creator_id}, quality={self.quality_score:.2f})'

class RecommendationImpression(models.Model):
    """
    Logs every time a recommendation is physically shown to a user.
    This enables the feedback loop: we know *why* we showed it, and we can 
    measure if the user responded positively.
    """
    user_id = models.PositiveBigIntegerField(db_index=True)
    content_id = models.PositiveBigIntegerField()
    content_type = models.CharField(max_length=10, default='reel')
    
    # Why was it recommended?
    candidate_source = models.CharField(max_length=50, help_text="e.g. SOCIAL_GRAPH, TRENDING, EXPLORE")
    source_user_id = models.PositiveBigIntegerField(null=True, blank=True, help_text="If recommended because of a friend")
    
    # Internal metrics at time of ranking
    recommendation_score = models.FloatField(default=0.0)
    model_version = models.CharField(max_length=50, default='v1.0')
    
    # Context
    session_id = models.UUIDField(null=True, blank=True)
    position = models.IntegerField(default=0)
    
    shown_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['user_id', 'content_id']),
            models.Index(fields=['session_id']),
        ]

    def __str__(self):
        return f"Impression(user={self.user_id}, content={self.content_id}, src={self.candidate_source})"

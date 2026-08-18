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
        unique=True, db_index=True,
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

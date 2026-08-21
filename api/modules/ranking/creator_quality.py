"""
Creator Quality Scoring
=======================
Calculates an aggregate quality score for content creators based on
engagement across all their content. Runs periodically (e.g., hourly).
"""

import logging
from datetime import timedelta
from django.utils import timezone
from celery import shared_task
from django.db.models import Count, Avg, Q, F

logger = logging.getLogger(__name__)

@shared_task(name='api.modules.ranking.creator_quality.compute_creator_quality')
def compute_creator_quality():
    """
    Computes creator quality metrics from the last 7 days of events.
    Writes results to the CreatorScore table.
    """
    from api.modules.rec_events.models import RecEvent
    from .models import CreatorScore
    
    lookback = timezone.now() - timedelta(days=7)
    
    # 1. We need events that have a creator_id
    # Optimize by doing aggregation in database if possible, or fetch and process in Python.
    # Since we need nuanced metrics (watch_pct), doing some aggregation in Python might be easier,
    # but let's try DB aggregation for speed.
    
    events_qs = RecEvent.objects.filter(
        timestamp__gte=lookback,
        creator_id__isnull=False,
        is_flagged=False
    )
    
    # Let's get the distinct creator IDs who had activity in the last 7 days
    active_creators = events_qs.values_list('creator_id', flat=True).distinct()
    
    if not active_creators:
        logger.info('compute_creator_quality: no active creators to score.')
        return {'creators_scored': 0}
        
    updated = 0
    
    for creator_id in active_creators:
        creator_events = events_qs.filter(creator_id=creator_id)
        
        total_events = creator_events.count()
        if total_events < 10:
            # Not enough data to score accurately, skip or assign default
            continue
            
        stats = creator_events.aggregate(
            avg_watch=Avg('watch_pct', filter=Q(event_type__in=['watch', 'replay', 'rewatch', 'rewatch_complete'])),
            shares=Count('event_id', filter=Q(event_type='share')),
            saves=Count('event_id', filter=Q(event_type='save')),
            reports=Count('event_id', filter=Q(event_type='report')),
            skips=Count('event_id', filter=Q(event_type='skip'))
        )
        
        # Calculate rates
        avg_completion = stats['avg_watch'] or 0.0
        share_rate = stats['shares'] / total_events
        save_rate = stats['saves'] / total_events
        report_rate = stats['reports'] / total_events
        
        # Determine upload frequency (simplified: just total events for now as proxy, 
        # normally we'd query the Reel/Post table directly for upload counts).
        upload_count_30d = 0 # Placeholder unless we query the Content tables directly
        
        # Combine into a single quality score (0-100 scale)
        quality_score = (
            (avg_completion * 40.0) +      # up to 40 points for completion
            (min(share_rate * 10, 1.0) * 30.0) + # up to 30 points for shares (capped at 10% share rate)
            (min(save_rate * 10, 1.0) * 30.0)    # up to 30 points for saves (capped at 10% save rate)
        )
        
        # Heavy penalty for reports
        quality_score -= (report_rate * 1000.0)
        
        # Bound score between 0 and 100
        quality_score = max(0.0, min(100.0, quality_score))
        
        CreatorScore.objects.update_or_create(
            creator_id=creator_id,
            defaults={
                'avg_completion_rate': avg_completion,
                'share_rate': share_rate,
                'save_rate': save_rate,
                'report_rate': report_rate,
                'upload_count_30d': upload_count_30d,
                'quality_score': quality_score
            }
        )
        updated += 1
        
    logger.info(f'compute_creator_quality: updated {updated} creators.')
    return {'creators_scored': updated}

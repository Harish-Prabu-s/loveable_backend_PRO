from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

RETENTION_DAYS = 90

@shared_task(name='api.modules.rec_privacy.tasks.purge_old_events')
def purge_old_events():
    """
    Celery Beat task to run daily.
    Deletes raw RecEvent records older than RETENTION_DAYS.
    Aggregated feature stores (UserInterestProfile, SessionLog) are kept
    as they do not contain raw identifiable event streams.
    """
    from api.modules.rec_events.models import RecEvent
    
    cutoff_date = timezone.now() - timedelta(days=RETENTION_DAYS)
    
    deleted_count, _ = RecEvent.objects.filter(timestamp__lt=cutoff_date).delete()
    
    logger.info(f"Privacy Purge: Deleted {deleted_count} raw recommendation events older than {RETENTION_DAYS} days.")
    return deleted_count

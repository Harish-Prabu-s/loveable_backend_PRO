from ...models import Offer
from django.db import models
from django.utils import timezone

def list_active_offers():
    now = timezone.now()
    return Offer.objects.filter(is_active=True).filter(
        (models.Q(start_time__isnull=True) | models.Q(start_time__lte=now)) &
        (models.Q(end_time__isnull=True) | models.Q(end_time__gte=now))
    )

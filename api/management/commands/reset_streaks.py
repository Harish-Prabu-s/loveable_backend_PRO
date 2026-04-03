from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.models import Streak

class Command(BaseCommand):
    help = 'Resets streaks that haven\'t seen an upload in over 24 hours'

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        
        # Identify streaks where last interaction is older than 24h
        streaks_to_reset = Streak.objects.filter(
            last_interaction_date__lt=threshold,
            streak_count__gt=0
        )
        
        count = streaks_to_reset.count()
        
        # Update them
        streaks_to_reset.update(
            streak_count=0,
            last_uploader=None
        )
        
        self.stdout.write(self.style.SUCCESS(f'Successfully reset {count} streaks.'))

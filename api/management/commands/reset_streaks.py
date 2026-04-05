from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from api.models import Streak

class Command(BaseCommand):
    help = 'Resets streaks that haven\'t seen an interaction in over 24 hours'

    def handle(self, *args, **options):
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        
        # Identify streaks where last interaction is older than 24h
        streaks = Streak.objects.filter(
            last_interaction_date__lt=threshold,
            streak_count__gt=0
        )
        
        reset_count = 0
        freeze_count = 0
        
        for s in streaks:
            if s.freezes_available > 0:
                s.freezes_available -= 1
                # Push last interaction forward to "consume" the freeze
                s.last_interaction_date = s.last_interaction_date + timedelta(hours=24)
                s.save()
                freeze_count += 1
            else:
                s.streak_count = 0
                s.last_uploader = None
                s.save()
                reset_count += 1
        
        self.stdout.write(self.style.SUCCESS(
            f'Successfully processed streaks: {reset_count} reset, {freeze_count} frozen.'
        ))

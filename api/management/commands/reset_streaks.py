from django.core.management.base import BaseCommand
from django.utils import timezone
from api.models import Streak

class Command(BaseCommand):
    help = 'Resets or freezes streaks that have expired (more than 24h since last interaction)'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        streaks = Streak.objects.filter(streak_count__gte=1)
        
        expired_count = 0
        frozen_count = 0
        
        for streak in streaks:
            if streak.last_interaction_date:
                delta = now - streak.last_interaction_date
                
                # Check if missed a full calendar day
                if delta.days > 0 and now.date() > streak.last_interaction_date.date():
                    if streak.freezes_available > 0:
                        streak.freezes_available -= 1
                        streak.last_interaction_date = now # bump date to avoid infinite freezing
                        streak.save()
                        frozen_count += 1
                        self.stdout.write(f"Froze streak for System Users {streak.user1.id} <-> {streak.user2.id}. Freezes left: {streak.freezes_available}")
                    else:
                        streak.streak_count = 0
                        streak.save()
                        expired_count += 1
                        self.stdout.write(f"Reset streak for System Users {streak.user1.id} <-> {streak.user2.id}")
                        
        self.stdout.write(self.style.SUCCESS(f'Successfully processed streaks. Expired: {expired_count}, Frozen: {frozen_count}'))

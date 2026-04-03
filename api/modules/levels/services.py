from django.contrib.auth.models import User
from ...models import LevelProgress

def get_level_progress(user: User):
    lp, _ = LevelProgress.objects.get_or_create(user=user)
    return lp

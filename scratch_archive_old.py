import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
import django
django.setup()
from api.models import Reel, Story

print("Archiving old broken reels and stories...")
reels_archived = Reel.objects.filter(is_archived=False).update(is_archived=True)
stories_archived = Story.objects.all().delete() # stories don't have is_archived, just delete them if they are broken

print(f"Archived {reels_archived} reels.")
print(f"Deleted old stories.")

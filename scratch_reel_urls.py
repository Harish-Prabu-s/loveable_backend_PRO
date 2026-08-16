import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
import django
django.setup()
from api.models import Reel
from api.serializers import ReelSerializer
from rest_framework.test import APIRequestFactory
from django.contrib.auth.models import AnonymousUser

factory = APIRequestFactory()
request = factory.get('/')
request.user = AnonymousUser()

print("=== Latest 3 Reels ===")
for reel in Reel.objects.order_by('-id')[:3]:
    serializer = ReelSerializer(reel, context={'request': request})
    data = serializer.data
    print(f"Reel ID: {data['id']}")
    print(f"Video URL: {data['video_url']}")
    if data['audio_details']:
        print(f"Audio URL: {data['audio_details'].get('url')}")
        print(f"Audio Provider: {data['audio_details'].get('provider')}")
    else:
        print("Audio URL: None")
    print("-" * 30)

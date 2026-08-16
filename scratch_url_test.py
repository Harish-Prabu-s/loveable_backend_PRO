import os
import requests
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
import django
django.setup()
from api.models import Post

post = Post.objects.filter(image__isnull=False).last()
if post and post.image:
    url = post.image.url
    print("Post Image URL:", url)
    try:
        response = requests.get(url)
        print("HTTP GET Status Code:", response.status_code)
        if response.status_code != 200:
            print("Response text:", response.text[:200])
    except Exception as e:
        print("Error fetching URL:", e)
else:
    print("No posts with images found.")

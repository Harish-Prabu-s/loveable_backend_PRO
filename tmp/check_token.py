import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from api.models import PushToken, User
from django.contrib.auth.models import User

# Searching for the user first
u = User.objects.filter(username__contains='7904067891').first()
if not u:
    print("User not found.")
else:
    # Now searching for the token
    pt = PushToken.objects.filter(user=u).order_by('-id').first()
    if pt:
        print(f"Token: {pt.expo_token}")
        print(f"Registered on: {pt.id} (last ID)")
        if hasattr(pt, 'created_at'):
            print(f"Created at: {pt.created_at}")
    else:
        print("No PushToken found for this user.")

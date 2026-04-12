import os
import sys
import django
import traceback

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.modules.chat.services import send_message
from django.contrib.auth.models import User

try:
    u = User.objects.get(id=2)  # Harish
    msg = send_message(room_id=5, sender=u, content='test', msg_type='text')
    print("Success:", msg)
except Exception as e:
    traceback.print_exc()

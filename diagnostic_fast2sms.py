import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from django.conf import settings
from api.modules.auth.utils_fast2sms import send_fast2sms_otp, send_fast2sms_otp_get

phone = "7904067891"
otp = "123456"

print(f"Testing Fast2SMS for {phone}...")
print(f"API KEY: {settings.FAST2SMS_API_KEY[:5]}...")

print("\n--- Testing POST (route: q) ---")
res_post = send_fast2sms_otp(phone, otp)
print(f"Result: {res_post}")

print("\n--- Testing GET (route: otp) ---")
res_get = send_fast2sms_otp_get(phone, otp)
print(f"Result: {res_get}")

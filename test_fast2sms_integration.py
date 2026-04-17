import os
import django
import sys

# Setup Django environment
sys.path.append('d:/loveable_app/react-to-android/backend')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.modules.auth.services import generate_and_store_otp_fast2sms

phone = "7904067891"
print(f"Testing generate_and_store_otp_fast2sms for {phone}...")
try:
    otp = generate_and_store_otp_fast2sms(phone)
    print(f"Result: OTP {otp} generated and sent (check logs/SMS)")
except Exception as e:
    print(f"Error: {e}")

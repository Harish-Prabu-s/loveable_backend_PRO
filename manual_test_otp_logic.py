import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from api.modules.auth.services import generate_and_store_otp

phone = "7904067891"
print(f"Manually calling generate_and_store_otp for {phone}...")
try:
    res = generate_and_store_otp(phone)
    print(f"Result: {res}")
except Exception as e:
    print(f"Exception: {e}")

# Check for log file
log_path = 'otp_debug.log'
if os.path.exists(log_path):
    print("\n--- Log File Content ---")
    with open(log_path, 'r') as f:
        print(f.read())
else:
    print("\nLog file was NOT created.")

import os
import sys

# Setup Django environment AT THE VERY TOP
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
import django
django.setup()

import json
from rest_framework.test import APIClient

def test_send_otp():
    client = APIClient()
    url = '/api/auth/send-otp/'
    # Use the phone number provided earlier
    data = {
        'phone_number': '7904067891',
        'channel': 'sms'
    }
    
    print(f"Testing POST {url} with data: {data}")
    try:
        response = client.post(url, data, format='json')
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {json.dumps(response.data, indent=2)}")
    except Exception as e:
        print(f"Error during API call: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_send_otp()

import os
import django
import sys
import json
from rest_framework.test import APIClient

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

def test_send_otp():
    client = APIClient()
    url = '/api/auth/send-otp/'
    data = {
        'phone_number': '7904067891',
        'channel': 'sms'
    }
    
    print(f"Testing POST {url} with data: {data}")
    response = client.post(url, data, format='json')
    
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {json.dumps(response.data, indent=2)}")

if __name__ == "__main__":
    test_send_otp()

import requests
from django.conf import settings

def send_ebdsms_otp(phone_number, otp):
    """
    Sends OTP via eBDSMS service.
    Requires 'EBDSMS_API_KEY' and 'EBDSMS_DEVICE_ID' in settings.
    """
    api_key = getattr(settings, 'EBDSMS_API_KEY', None)
    device_id = getattr(settings, 'EBDSMS_DEVICE_ID', None)
    
    if not api_key or not device_id:
        return {'success': False, 'error': 'EBDSMS_API_KEY or EBDSMS_DEVICE_ID not configured'}

    # eBDSMS expects numbers without country code for some regions, 
    # but let's strip + just in case as their docs show examples like 017...
    # If the user provides +91..., we might need to adjust based on their specific requirement.
    # For now, we will send as is or strip + if it causes issues.
    clean_number = phone_number.replace('+', '')

    url = "https://client.ebdsms.com/services/send.php"
    
    params = {
        'key': api_key,
        'number': clean_number,
        'message': f"Your OTP is {otp}",
        'devices': device_id,
        'type': 'sms',
        'prioritize': '0'
    }

    try:
        response = requests.get(url, params=params)
        # Check if response status is 200 (OK)
        if response.status_code == 200:
             # The API returns the message body directly
            return {'success': True, 'response': response.text}
        else:
            return {'success': False, 'error': f"Status {response.status_code}"}
    except Exception as e:
        return {'success': False, 'error': str(e)}

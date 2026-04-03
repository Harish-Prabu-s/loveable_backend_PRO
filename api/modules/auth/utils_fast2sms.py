import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_fast2sms_otp(phone_number, otp):
    """
    Sends OTP via Fast2SMS service using POST method.
    Requires 'FAST2SMS_API_KEY' in settings.
    """
    api_key = getattr(settings, 'FAST2SMS_API_KEY', None)
    
    if not api_key:
        return {'success': False, 'error': 'FAST2SMS_API_KEY not configured'}

    # Fast2SMS expects numbers as a comma-separated string
    # Ensure phone number is clean (no + sign)
    clean_number = phone_number.replace('+', '')
    if clean_number.startswith('91') and len(clean_number) > 10:
        clean_number = clean_number[2:] # Fast2SMS usually expects 10 digits for India if route is otp

    url = "https://www.fast2sms.com/dev/bulkV2"
    
    headers = {
        "authorization": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "route": "otp",
        "variables_values": str(otp),
        "numbers": clean_number,
        "flash": "0"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response_data = response.json()
        
        # Log the full response for debugging
        print(f"\n--- Fast2SMS POST Response for {phone_number} ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response_data}")
        print("-------------------------------------------\n")
        
        if response.status_code == 200 and response_data.get('return'):
            logger.info(f"Fast2SMS OTP sent successfully to {phone_number}")
            return {'success': True, 'response': response_data}
        else:
            error_msg = response_data.get('message', 'Unknown error')
            logger.error(f"Fast2SMS error: {error_msg}")
            return {'success': False, 'error': error_msg}
    except Exception as e:
        logger.error(f"Fast2SMS exception: {str(e)}")
        return {'success': False, 'error': str(e)}

def send_fast2sms_otp_get(phone_number, otp):
    """
    Sends OTP via Fast2SMS service using GET method.
    """
    api_key = getattr(settings, 'FAST2SMS_API_KEY', None)
    
    if not api_key:
        return {'success': False, 'error': 'FAST2SMS_API_KEY not configured'}

    clean_number = phone_number.replace('+', '')
    if clean_number.startswith('91') and len(clean_number) > 10:
        clean_number = clean_number[2:]

    url = "https://www.fast2sms.com/dev/bulkV2"
    
    params = {
        "authorization": api_key,
        "route": "otp",
        "variables_values": str(otp),
        "numbers": clean_number,
        "flash": "0"
    }

    try:
        response = requests.get(url, params=params)
        response_data = response.json()
        
        # Log the full response for debugging
        print(f"\n--- Fast2SMS GET Response for {phone_number} ---")
        print(f"Status Code: {response.status_code}")
        print(f"Response Body: {response_data}")
        print("------------------------------------------\n")
        
        if response.status_code == 200 and response_data.get('return'):
            return {'success': True, 'response': response_data}
        else:
            return {'success': False, 'error': response_data.get('message', 'Unknown error')}
    except Exception as e:
        return {'success': False, 'error': str(e)}

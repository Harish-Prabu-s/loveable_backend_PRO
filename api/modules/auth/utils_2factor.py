import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def send_otp_2factor(phone_number: str):
    """
    Sends OTP via 2Factor.in API.
    API: https://2factor.in/API/V1/{api_key}/SMS/{phone_number}/AUTOGEN
    """
    api_key = settings.TWOFACTOR_API_KEY
    if not api_key:
        logger.error("TWOFACTOR_API_KEY not configured")
        return None

    # Normalize phone number: 2Factor usually expects local number or full number without +?
    # Docs say: 10 digit number for India, or with country code for international.
    # Let's strip '+' if present.
    phone = phone_number.replace('+', '')
    
    url = f"https://2factor.in/API/V1/{api_key}/SMS/{phone}/AUTOGEN"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # Success response: {"Status": "Success", "Details": "SessionId"}
        if data.get('Status') == 'Success':
            session_id = data.get('Details')
            logger.info(f"2Factor OTP sent to {phone}. SessionId: {session_id}")
            return session_id
        else:
            logger.error(f"2Factor OTP failed: {data}")
            return None
    except Exception as e:
        logger.error(f"2Factor API Error: {e}")
        return None

def verify_otp_2factor_service(session_id: str, otp_input: str):
    """
    Verifies OTP via 2Factor.in API.
    API: https://2factor.in/API/V1/{api_key}/SMS/VERIFY/{session_id}/{otp_input}
    """
    api_key = settings.TWOFACTOR_API_KEY
    if not api_key:
        return False
        
    url = f"https://2factor.in/API/V1/{api_key}/SMS/VERIFY/{session_id}/{otp_input}"
    
    try:
        response = requests.get(url)
        data = response.json()
        
        # Success response: {"Status": "Success", "Details": "OTP Matched"}
        if data.get('Status') == 'Success' and data.get('Details') == 'OTP Matched':
            return True
        else:
            logger.warning(f"2Factor Verify Failed: {data}")
            return False
    except Exception as e:
        logger.error(f"2Factor Verify Error: {e}")
        return False

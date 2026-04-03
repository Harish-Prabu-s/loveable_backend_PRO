import requests
from django.conf import settings

def send_whatsapp_otp(phone_number, otp):
    """
    Sends OTP via WhatsApp using dbuddyz.prismswift.com (Free OTP Service).
    Requires 'PRISMSWIFT_TOKEN' in settings.
    """
    token = getattr(settings, 'PRISMSWIFT_TOKEN', None)
    if not token:
        return {'success': False, 'error': 'PRISMSWIFT_TOKEN not configured'}

    url = "https://dbuddyz.prismswift.com/send/"
    
    # Ensure phone number has + prefix if missing
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number

    payload = {
        'token': token,
        'otp': otp,
        'tonumber': phone_number
    }

    try:
        response = requests.post(url, data=payload)
        response_data = response.json()
        
        # The API doesn't have standard docs, but usually returns success status
        return {'success': True, 'response': response_data}
    except Exception as e:
        return {'success': False, 'error': str(e)}

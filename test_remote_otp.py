import requests
import json

def test_remote_otp():
    # SET YOUR PHONE NUMBER HERE
    my_phone = "YOUR_PHONE_NUMBER" 
    url = "https://loveable.sbs/api/auth/send-otp/"
    data = {"phone_number": my_phone, "channel": "sms"}
    headers = {"Content-Type": "application/json"}
    
    print(f"Hitting Remote URL: {url}")
    print(f"Data: {data}")
    
    try:
        # Increased timeout to 30s
        response = requests.post(url, json=data, headers=headers, timeout=30)
        print(f"Status Code: {response.status_code}")
        print(f"Response JSON: {json.dumps(response.json(), indent=2)}")
    except Exception as e:
        print(f"Error hitting remote URL: {e}")

if __name__ == "__main__":
    test_remote_otp()

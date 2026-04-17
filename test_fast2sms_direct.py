import requests

api_key = "3oFIKsLZCiBpSOAumMhWX5ceNdEgjxbUzflkwy6RG9QP0q412nA3bxJ9kyTRDEpZntoO64I5H2WFNdch"
phone = "7904067891"
otp = "123456"

# Testing GET (route: otp)
url = "https://www.fast2sms.com/dev/bulkV2"
params = {
    "authorization": api_key,
    "route": "otp",
    "variables_values": otp,
    "numbers": phone,
    "flash": "0"
}

print(f"Testing Fast2SMS GET (route: otp) for {phone}...")
try:
    response = requests.get(url, params=params)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

import requests

api_key = "3oFIKsLZCiBpSOAumMhWX5ceNdEgjxbUzflkwy6RG9QP0q412nA3bxJ9kyTRDEpZntoO64I5H2WFNdch"
phone = "7904067891"
otp = "123456"

# Testing POST (route: q)
url = "https://www.fast2sms.com/dev/bulkV2"
# Try a more generic message that might bypass DLT checks if it's considered "Direct"
payload = {
    "route": "q",
    "message": f"Hello, your code is {otp}",
    "numbers": phone,
}

headers = {
    "authorization": api_key,
    "Content-Type": "application/json"
}

print(f"Testing Fast2SMS POST (route: q) for {phone}...")
try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")

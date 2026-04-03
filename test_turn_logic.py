import hmac
import hashlib
import base64
import time

def test_turn_credentials():
    secret = "CHANGEME_SECURE_SECRET_RANDOM_STRING"
    user_id = 123
    ttl = 24 * 3600
    timestamp = int(time.time()) + ttl
    username = f"{timestamp}:{user_id}"
    
    dig = hmac.new(
        secret.encode('utf-8'),
        username.encode('utf-8'),
        hashlib.sha1
    ).digest()
    
    password = base64.b64encode(dig).decode('utf-8')
    
    print(f"Username: {username}")
    print(f"Password: {password}")
    print("Verification: Password is base64 and not empty.")
    assert len(password) > 0
    assert ":" in username

if __name__ == "__main__":
    test_turn_credentials()

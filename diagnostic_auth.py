import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')
django.setup()

from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from api.models import Profile

def diagnostic():
    user = User.objects.filter(id=175).first()
    if not user:
        print("User 175 NOT FOUND")
        # Check latest user
        user = User.objects.latest('id')
        print(f"Latest User: ID={user.id}, Username={user.username}")
    else:
        print(f"User 175 FOUND: {user.username}")
    
    profile = user.profile
    print(f"Profile: ID={profile.id}, Verified={profile.is_verified}, Name='{profile.display_name}', Gender={profile.gender}")
    
    # Generate a token manually
    refresh = RefreshToken.for_user(user)
    token = str(refresh.access_token)
    print(f"Manual Token Generated for User {user.id}")
    
    # Try to verify it (internal)
    from rest_framework_simplejwt.authentication import JWTAuthentication
    from rest_framework.test import APIRequestFactory
    
    factory = APIRequestFactory()
    request = factory.get('/api/profiles/me/', HTTP_AUTHORIZATION=f'Bearer {token}')
    
    auth = JWTAuthentication()
    try:
        validated_token = auth.get_validated_token(token)
        authed_user = auth.get_user(validated_token)
        print(f"Internal Token Verification SUCCESS: User={authed_user.id}")
    except Exception as e:
        print(f"Internal Token Verification FAILED: {e}")

if __name__ == "__main__":
    diagnostic()

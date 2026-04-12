import os
from pathlib import Path
from dotenv import load_dotenv
import pymysql

pymysql.install_as_MySQLdb()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(os.path.join(BASE_DIR, '.env'))

# --- DIAGNOSTIC MIDDLEWARE ---
class AuthDebugMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        try:
            auth = request.META.get('HTTP_AUTHORIZATION', 'NONE')
            # Only log first 20 chars of token for security
            bearer = auth[:20] if len(auth) > 20 else auth
            print(f"AG_DEBUG: [{request.method}] {request.path} | Auth: {bearer}")
        except Exception as e:
            print(f"AG_DEBUG_ERR: Pre-request logging failed: {e}")

        try:
            response = self.get_response(request)
            
            # Safe access to response status
            status_code = getattr(response, 'status_code', 'UNKNOWN')
            print(f"AG_DEBUG: Response: {status_code}")
            
            # If 401/500, check if user was authenticated safely
            if status_code in (401, 500):
                user_info = "N/A"
                if hasattr(request, 'user'):
                    user_info = str(request.user)
                print(f"AG_DEBUG: {status_code} Detail - User: {user_info}")
                
            return response
        except Exception as e:
            import traceback
            print(f"AG_DEBUG_CRITICAL: Request failed with error: {e}")
            traceback.print_exc()
            raise # Re-raise to let Django handle the 500 properly
# -----------------------------

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-secret-key')
DEBUG = True
ALLOWED_HOSTS = ['*', 'loveable.sbs', '72.62.195.63', '74.220.48.249', '192.168.1.4', '10.130.45.184']
CSRF_TRUSTED_ORIGINS = [
    'https://loveable.sbs',
    'https://*.ngrok-free.dev',
    'https://berneice-untransmigrated-exotically.ngrok-free.dev'
]

# 🔒 HTTPS / SSL Proxy Settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

# Production Security
if os.environ.get('ENV') == 'production':
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',
    'channels',
    'api',
]

MIDDLEWARE = [
    'vibely_backend.settings.AuthDebugMiddleware', # Diagnostic first
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'vibely_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'vibely_backend.wsgi.application'
ASGI_APPLICATION = 'vibely_backend.asgi.application'

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379')

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
            # Separate namespace so channel messages don't collide with cache keys
            "prefix": "vibely",
            # Expire stale channel groups after 24h
            "group_expiry": 86400,
            # Cap channel message queue at 100 to prevent memory bloat
            "capacity": 100,
        },
    },
}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'loveable',
        'USER': 'harish',
        'PASSWORD': 'Harish@123',
        'HOST': '72.62.195.63',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'static_root'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

from datetime import timedelta

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    )
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=7),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=30),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'AUTH_HEADER_NAME': 'HTTP_AUTHORIZATION',
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

# Email Settings (Gmail)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'loveable.comnect@gmail.com')
# Generate App Password: https://myaccount.google.com/apppasswords
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'syjn spew wwxn jrgs')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER

# CORS
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://loveable.sbs",
]
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# Media (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Razorpay Configuration
# Replace with your actual keys from Razorpay Dashboard
# RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', 'rzp_test_YourKeyHere')
# RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', 'YourSecretHere')

# Razorpay Settings
# RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID', '')
# RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET', '')
RAZORPAY_KEY_ID = 'rzp_test_SNqKIEWV9NSYuU'
RAZORPAY_KEY_SECRET = '0OMicPadM4h7denXPCIF9Jd6'

# SMS Settings (Twilio)
# NOTE: TWILIO_ACCOUNT_SID must start with 'AC'.
# Ensure TWILIO_AUTH_TOKEN is updated to match the new SID.
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', '')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_WHATSAPP_NUMBER', '')
TWILIO_PHONE_NUMBER_SID = os.environ.get('TWILIO_PHONE_NUMBER_SID', '')
TWILIO_VERIFY_SID = os.environ.get('TWILIO_VERIFY_SID', '')

# MSG91 Settings
MSG91_AUTH_KEY = os.environ.get('MSG91_AUTH_KEY', '')
MSG91_TEMPLATE_ID = os.environ.get('MSG91_TEMPLATE_ID', '')

# 2Factor Settings
TWOFACTOR_API_KEY = os.environ.get('TWOFACTOR_API_KEY', '')

# PrismSwift (WhatsApp OTP) Settings
# Get token from: https://dbuddyz.prismswift.com/dashboard/
PRISMSWIFT_TOKEN = os.environ.get('PRISMSWIFT_TOKEN', '')

# eBDSMS Settings
EBDSMS_API_KEY = os.environ.get('EBDSMS_API_KEY', '')
EBDSMS_DEVICE_ID = os.environ.get('EBDSMS_DEVICE_ID', '')

# Spotify Settings
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID', '')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')

# Fast2SMS Settings
FAST2SMS_API_KEY = os.environ.get('FAST2SMS_API_KEY', '')

# ==============================================================================
# SENIOR BACKEND ARCHITECT: PRODUCTION READINESS GUIDE
# ==============================================================================
# To scale this system to millions of users, follow these mandatory steps:
#
# 1. DATABASE:
#    - Switch from 'sqlite3' to 'postgresql'.
#    - Add 'CONN_MAX_AGE: 60' to database settings to reuse connections.
#    - Ensure all queried fields have 'db_index=True' in models.py.
#
# 2. CACHING & REAL-TIME:
#    - Change CHANNEL_LAYERS from 'InMemoryChannelLayer' to 'RedisChannelLayer'.
#    - Implement 'django-redis' as the DEFAULT CACHE backend.
#    - Cache frequently accessed data like user profiles and top leaderboards.
#
# 3. ASYNC WORKERS:
#    - Introduce Celery or Django-Q for background tasks.
#    - Offload push notifications and "Notify Close Friends" loops to workers.
#
# 4. PERFORMANCE MONITORING:
#    - Install 'django-debug-toolbar' in dev to monitor N+1 queries.
#    - Use 'Sentry' or 'New Relic' in production for APM.
#
# 5. SECURITY HARDENING:
#    - Set 'DEBUG = False'.
#    - Enable 'AUTH_PASSWORD_VALIDATORS'.
#    - Set 'SECURE_SSL_REDIRECT = True' and use proper 'CORS_ALLOWED_ORIGINS'.
# ==============================================================================

# Allow Large Video Reels Uploads
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB

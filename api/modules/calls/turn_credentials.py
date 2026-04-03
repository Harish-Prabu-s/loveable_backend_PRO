"""
TURN Server Credential Generation
===================================
Generates time-limited HMAC credentials for Coturn (self-hosted TURN server).

The algorithm is the standard REST API secret method supported by Coturn:
  - username = "<unix_timestamp_expiry>:<user_id>"
  - credential = HMAC-SHA1(TURN_STATIC_SECRET, username) → base64

The credential expires at <unix_timestamp_expiry>. Coturn verifies this
automatically. This prevents credential replay attacks.

Security notes:
  - TURN_STATIC_SECRET must be a strong random secret (>32 chars)
  - Credentials are scoped to the authenticated user's ID
  - TTL defaults to 24 hours; reduce for higher security
"""
import hashlib
import hmac
import base64
import time
import os

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


TURN_SECRET = os.environ.get('TURN_STATIC_SECRET', 'CHANGEME_SECURE_SECRET_RANDOM_STRING')
TURN_REALM  = os.environ.get('TURN_REALM', 'loveable-turn')
TURN_HOST   = os.environ.get('TURN_HOST', 'turn.loveable.sbs')
TURN_TTL    = int(os.environ.get('TURN_TTL_SECONDS', 86400))  # 24 hours


def _generate_hmac_credentials(user_id: str) -> dict:
    """Generate time-limited TURN credentials using HMAC-SHA1."""
    expiry = int(time.time()) + TURN_TTL
    username = f"{expiry}:{user_id}"

    # HMAC-SHA1 is what Coturn expects when use-auth-secret is configured
    raw_hmac = hmac.new(
        key=TURN_SECRET.encode('utf-8'),
        msg=username.encode('utf-8'),
        digestmod=hashlib.sha1
    ).digest()
    credential = base64.b64encode(raw_hmac).decode('utf-8')

    return {
        'username': username,
        'credential': credential,
        'ttl': TURN_TTL,
        'uris': [
            f'stun:{TURN_HOST}:3478',
            f'turn:{TURN_HOST}:3478?transport=udp',
            f'turn:{TURN_HOST}:3478?transport=tcp',
            f'turns:{TURN_HOST}:5349?transport=tcp',   # TLS fallback
        ],
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_turn_credentials(request):
    """
    GET /api/calls/turn-credentials/

    Returns TURN server credentials for the authenticated user.
    Credentials are time-limited and scoped to the user's ID.

    Response:
        {
            "iceServers": [
                { "urls": "stun:...", "username": "...", "credential": "..." },
                { "urls": ["turn:...", "turns:..."], "username": "...", "credential": "..." }
            ],
            "ttl": 86400
        }
    """
    user_id = str(request.user.id)
    creds = _generate_hmac_credentials(user_id)

    # Format as RTCConfiguration.iceServers array expected by browsers
    ice_servers = [
        # Google STUN as primary fast path
        {'urls': 'stun:stun.l.google.com:19302'},
        {'urls': 'stun:stun1.l.google.com:19302'},
        # Our TURN server
        {
            'urls': creds['uris'],
            'username': creds['username'],
            'credential': creds['credential'],
        },
    ]

    return Response({
        'iceServers': ice_servers,
        'ttl': creds['ttl'],
    })

import hmac
import hashlib
import base64
import time
import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.contrib.auth.models import User
from api.models import CallSession
from .serializers import CallSessionSerializer
from .services import initiate_call, end_call, accept_call


class InitiateCallView(APIView):
    """POST /api/calls/initiate/ — start a call session."""

    def post(self, request):
        callee_id = request.data.get('callee_id')
        call_type = request.data.get('call_type', 'VOICE').upper()  # VOICE or VIDEO
        room_id = request.data.get('room_id')

        if not callee_id:
            return Response({'detail': 'callee_id required.'}, status=400)
        if call_type not in ('VOICE', 'VIDEO'):
            return Response({'detail': 'call_type must be VOICE or VIDEO.'}, status=400)

        try:
            callee = User.objects.get(pk=callee_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=404)

        if callee == request.user:
            return Response({'detail': 'Cannot call yourself.'}, status=400)

        try:
            session = initiate_call(request.user, callee, call_type, room_id)
        except PermissionError as e:
            return Response({'detail': str(e)}, status=403)

        return Response(CallSessionSerializer(session).data, status=201)


class AcceptCallView(APIView):
    """POST /api/calls/accept/ — accept an incoming call session."""

    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'detail': 'session_id required.'}, status=400)

        try:
            session = CallSession.objects.get(pk=session_id)
        except CallSession.DoesNotExist:
            return Response({'detail': 'Session not found.'}, status=404)

        if session.callee != request.user:
            return Response({'detail': 'Not your call to accept.'}, status=403)

        session = accept_call(session)
        return Response(CallSessionSerializer(session).data)


class EndCallView(APIView):
    """POST /api/calls/end/ — end a call session."""

    def post(self, request):
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'detail': 'session_id required.'}, status=400)

        try:
            session = CallSession.objects.get(pk=session_id)
        except CallSession.DoesNotExist:
            return Response({'detail': 'Session not found.'}, status=404)

        if session.caller != request.user and session.callee != request.user:
            return Response({'detail': 'Not your call.'}, status=403)

        result = end_call(session)
        return Response(result)



class CallLogsView(APIView):
    """GET /api/calls/logs/ — call history for the current user."""

    def get(self, request):
        sessions = (
            CallSession.objects
            .filter(caller=request.user) | CallSession.objects.filter(callee=request.user)
        ).order_by('-started_at')[:50]
        return Response(CallSessionSerializer(sessions, many=True).data)


class TurnCredentialsView(APIView):
    """
    GET /api/calls/turn-credentials/

    Generates time-limited HMAC-SHA1 credentials for Coturn.
    Credentials expire after TTL seconds (default 24h).
    Coturn must be configured with: use-auth-secret + static-auth-secret
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        turn_secret = os.environ.get('TURN_STATIC_SECRET', 'CHANGEME_SECURE_SECRET_RANDOM_STRING')
        turn_host   = os.environ.get('TURN_HOST', 'loveable.sbs')

        # Credentials valid for 24 hours
        ttl = 24 * 3600
        timestamp = int(time.time()) + ttl
        username = f"{timestamp}:{request.user.id}"

        # HMAC-SHA1 — the algorithm Coturn expects with use-auth-secret
        raw = hmac.new(
            turn_secret.encode('utf-8'),
            username.encode('utf-8'),
            hashlib.sha1
        ).digest()
        credential = base64.b64encode(raw).decode('utf-8')

        ice_servers = [
            # Fast STUN paths (no relay, free)
            {'urls': 'stun:stun.l.google.com:19302'},
            {'urls': 'stun:stun1.l.google.com:19302'},
            # Self-hosted TURN: UDP primary, TCP fallback, TLS secured fallback
            {
                'urls': [
                    f'turn:{turn_host}:3478?transport=udp',
                    f'turn:{turn_host}:3478?transport=tcp',
                    f'turns:{turn_host}:5349?transport=tcp',  # TLS — penetrates strict firewalls
                ],
                'username': username,
                'credential': credential,
            },
        ]

        return Response({
            'iceServers': ice_servers,
            'ttl': ttl,
        })

from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Support both root '/ws/' and prefixed '/api/ws/' automatically by matching the core path
    re_path(r'^/?(?:api/)?ws/notifications/(?P<user_id>[\w\-_]+)/?$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'^/?(?:api/)?ws/chat/(?P<user_id>[\w\-_]+)/?$', consumers.ChatConsumer.as_asgi()),
    re_path(r'^/?(?:api/)?ws/call/(?P<user_id>[\w\-_]+)/?$', consumers.CallConsumer.as_asgi()),
    
    # WebRTC Signaling path
    re_path(r'^/?(?:api/)?ws/call/room/(?P<room_id>[^/]+)/?$', consumers.CallRoomConsumer.as_asgi()),
]

from django.urls import re_path
from . import consumers
from ..games.social_game_consumer import SocialGameConsumer
from ..games.matchmaking_consumer import MatchmakingConsumer

websocket_urlpatterns = [
    # Notification path
    re_path(r'^/?(?:api/)?ws/notifications/(?P<user_id>[\w\-_]+)/?$', consumers.NotificationConsumer.as_asgi()),
    
    # Chat path
    re_path(r'^/?(?:api/)?ws/chat/(?P<user_id>[\w\-_]+)/?$', consumers.ChatConsumer.as_asgi()),
    
    # Call signaling path
    re_path(r'^/?(?:api/)?ws/call/(?P<user_id>[\w\-_]+)/?$', consumers.CallConsumer.as_asgi()),
    
    # WebRTC Signaling path
    re_path(r'^/?(?:api/)?ws/call/room/(?P<room_id>[^/]+)/?$', consumers.CallRoomConsumer.as_asgi()),

    # Unified Multi-Mode Social Game path
    re_path(r'^/?(?:api/)?ws/games/social/(?P<room_id>\w+)/?$', SocialGameConsumer.as_asgi()),

    # Matchmaking path
    re_path(r'^/?(?:api/)?ws/matchmaking/?$', MatchmakingConsumer.as_asgi()),
]

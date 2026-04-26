from django.urls import re_path
from . import consumers
from .truth_or_dare_consumer import TruthOrDareConsumer

websocket_urlpatterns = [
    # Match the core path part to handle both root and prefixed URLs
    re_path(r'^/?(?:api/)?ws/game/(?P<session_id>\d+)/?$', consumers.GameConsumer.as_asgi()),
    re_path(r'^/?(?:api/)?ws/game/truth_or_dare/(?P<session_id>\d+)/?$', TruthOrDareConsumer.as_asgi()),
    re_path(r'^/?(?:api/)?ws/game/couple/(?P<session_id>\d+)/?$', consumers.CoupleGameConsumer.as_asgi()),
    re_path(r'^/?(?:api/)?ws/matchmaking/?$', consumers.MatchmakingConsumer.as_asgi()),
]

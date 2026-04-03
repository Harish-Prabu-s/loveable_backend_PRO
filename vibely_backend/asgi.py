import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from api.modules.realtime.middleware import JWTAuthMiddlewareStack
import api.modules.realtime.routing
import api.modules.games.routing
from api.modules.realtime.consumers import CatchAllConsumer
from django.urls import re_path

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')

class TraceMiddleware:
    def __init__(self, inner):
        self.inner = inner
    async def __call__(self, scope, receive, send):
        path = scope.get('path', 'unknown')
        if "ws" in path:
            headers = {k.decode(): v.decode() for k, v in scope.get('headers', [])}
            version = scope.get('http_version', 'unknown')
            print(f"[TRACE] {scope['type'].upper()} request on {path} | Version: {version}")
            print(f"[TRACE] Headers: {headers}")
        return await self.inner(scope, receive, send)

application = TraceMiddleware(ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddlewareStack(
        URLRouter(
            api.modules.realtime.routing.websocket_urlpatterns +
            api.modules.games.routing.websocket_urlpatterns +
            [re_path(r'^.*$', CatchAllConsumer.as_asgi())]
        )
    ),
}))


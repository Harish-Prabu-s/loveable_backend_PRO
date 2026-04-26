from django.contrib import admin
from django.urls import path, include, re_path
from django.views.static import serve
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
import logging

def diagnostic_view(request, room_id=None):
    logger = logging.getLogger(__name__)
    headers = {k: v for k, v in request.META.items() if k.startswith('HTTP_') or k in ['CONTENT_TYPE', 'CONTENT_LENGTH']}
    logger.info(f"[HTTP SHADOW] Request on WS path detected! Room: {room_id}")
    logger.info(f"[HTTP SHADOW] Headers: {headers}")
    return JsonResponse({
        "error": "This path is reserved for WebSockets, yet it was hit as HTTP.",
        "hint": "Check if your proxy (ngrok) is correctly forwarding Upgrade/Connection headers.",
        "room_id": room_id
    }, status=426)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    # Diagnostic Trap: If these are hit, then the connection is failing to upgrade to WebSocket.
    path('ws/call/room/<str:room_id>/', diagnostic_view),
    path('api/ws/call/room/<str:room_id>/', diagnostic_view),
    path('ws/game/<str:room_id>/', diagnostic_view),
    path('api/ws/game/<str:room_id>/', diagnostic_view),
]

# Always serve media files via Django (fallback setup)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {
        'document_root': settings.MEDIA_ROOT,
    }),
]

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .controllers import AudioViewSet, list_audios_view, search_audios_view, get_synced_lyrics, toggle_favorite_line

router = DefaultRouter()
router.register(r'library', AudioViewSet, basename='audio-library')

urlpatterns = [
    path('', include(router.urls)),
    path('legacy/', list_audios_view, name='list_audios_legacy'),
    path('search/', search_audios_view, name='search_audios'),
    path('lyrics/<str:music_id>/', get_synced_lyrics, name='get_synced_lyrics'),
    path('lyrics/toggle_favorite/', toggle_favorite_line, name='toggle_favorite_lyric'),
]

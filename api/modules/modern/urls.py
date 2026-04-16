from django.urls import path, include
from rest_framework.routers import DefaultRouter
from api.views_modern import (
    MediaAssetViewSet, MusicTrackViewSet, EditorDraftViewSet, PublishViewSet
)

router = DefaultRouter()
router.register(r'assets', MediaAssetViewSet, basename='modern-assets')
router.register(r'music', MusicTrackViewSet, basename='modern-music')
router.register(r'drafts', EditorDraftViewSet, basename='modern-drafts')
router.register(r'publish', PublishViewSet, basename='modern-publish')

urlpatterns = [
    path('', include(router.urls)),
]

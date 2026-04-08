from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .controllers import HighlightViewSet

router = DefaultRouter()
router.register(r'', HighlightViewSet, basename='highlights')

urlpatterns = [
    path('', include(router.urls)),
]

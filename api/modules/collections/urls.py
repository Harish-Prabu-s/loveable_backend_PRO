from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .controllers import CollectionViewSet

router = DefaultRouter()
router.register(r'', CollectionViewSet, basename='collections')

urlpatterns = [
    path('', include(router.urls)),
]

from django.urls import path
from .controllers import friend_request, friend_accept, friend_reject

urlpatterns = [
    path('request', friend_request),
    path('request/', friend_request),
    path('accept', friend_accept),
    path('accept/', friend_accept),
    path('reject', friend_reject),
    path('reject/', friend_reject),
]

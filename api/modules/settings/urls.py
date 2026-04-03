from django.urls import path
from .controllers import get_settings, update_settings, verify_lock

urlpatterns = [
    path('', get_settings),
    path('update/', update_settings),
    path('verify-lock/', verify_lock),
]

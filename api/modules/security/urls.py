from django.urls import path
from . import controllers

urlpatterns = [
    path('set-lock/', controllers.set_app_lock),
    path('verify-lock/', controllers.verify_app_lock),
    path('update-settings/', controllers.update_security_settings),
    path('reset-init/', controllers.initiate_lock_reset),
    path('reset-verify/', controllers.verify_reset_otp),
]

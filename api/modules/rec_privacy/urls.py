from django.urls import path
from .views import PrivacyConsentView

urlpatterns = [
    path('privacy/consent/', PrivacyConsentView.as_view(), name='rec-privacy-consent'),
]

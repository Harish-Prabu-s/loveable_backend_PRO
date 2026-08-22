"""
Event Module URL Configuration
"""

from django.urls import path
from .views import EventIngestView, EventBatchIngestView
from .social_views import SocialEventIngestView

urlpatterns = [
    path('events/', EventIngestView.as_view(), name='rec-event-ingest'),
    path('events/batch/', EventBatchIngestView.as_view(), name='rec-event-batch-ingest'),
    path('social-events/', SocialEventIngestView.as_view(), name='social-event-ingest'),
]

"""
Event Module URL Configuration
"""

from django.urls import path
from .views import EventIngestView, EventBatchIngestView

urlpatterns = [
    path('events/', EventIngestView.as_view(), name='rec-event-ingest'),
    path('events/batch/', EventBatchIngestView.as_view(), name='rec-event-batch-ingest'),
]

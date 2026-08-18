"""
Recommendation Feed URL Configuration
"""

from django.urls import path
from .views import RecommendedFeedView

urlpatterns = [
    path('feed/', RecommendedFeedView.as_view(), name='rec-feed'),
]

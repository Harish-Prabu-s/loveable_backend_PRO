from django.urls import path
from .views import ExplicitFeedbackView, WhyAmISeeingThisView, ResetRecommendationsView

urlpatterns = [
    path('feedback/', ExplicitFeedbackView.as_view(), name='rec-feedback-action'),
    path('feedback/why/', WhyAmISeeingThisView.as_view(), name='rec-feedback-why'),
    path('feedback/reset/', ResetRecommendationsView.as_view(), name='rec-feedback-reset'),
]

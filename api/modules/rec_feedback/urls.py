from django.urls import path
from .views import ExplicitFeedbackView, WhyAmISeeingThisView, ResetRecommendationsView, InterestsView

urlpatterns = [
    path('feedback/', ExplicitFeedbackView.as_view(), name='rec-feedback-action'),
    path('feedback/why/', WhyAmISeeingThisView.as_view(), name='rec-feedback-why'),
    path('feedback/reset/', ResetRecommendationsView.as_view(), name='rec-feedback-reset'),
    path('feedback/interests/', InterestsView.as_view(), name='rec-feedback-interests'),
    path('feedback/interests/<str:topic>/', InterestsView.as_view(), name='rec-feedback-interests-detail'),
]

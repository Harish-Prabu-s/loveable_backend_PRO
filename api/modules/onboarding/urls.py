from django.urls import path
from . import views

urlpatterns = [
    path('interests/', views.OnboardingInterestsView.as_view(), name='onboarding_interests'),
]

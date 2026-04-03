from django.urls import path
from . import controllers

urlpatterns = [
    path('rules/', controllers.MonetizationRuleListView.as_view()),
    path('rules/<int:pk>/', controllers.MonetizationRuleDetailView.as_view()),
    path('pricing/', controllers.PricingLookupView.as_view()),
]

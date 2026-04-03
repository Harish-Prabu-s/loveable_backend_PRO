from django.urls import path
from . import controllers

urlpatterns = [
    path('create/', controllers.CreateBetMatchView.as_view()),
    path('join/<int:match_id>/', controllers.JoinBetMatchView.as_view()),
    path('result/<int:match_id>/', controllers.BetMatchResultView.as_view()),
    path('list/', controllers.BetMatchListView.as_view()),
]

from django.urls import path
from . import controllers

urlpatterns = [
    path('leaderboard/', controllers.LeaderboardView.as_view()),
    path('my-rank/', controllers.MyRankView.as_view()),
]

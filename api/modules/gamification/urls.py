from django.urls import path
from .controllers import level_view, daily_rewards_view, claim_daily_reward_view, leaderboard_view

urlpatterns = [
    path('level/', level_view),
    path('daily-rewards/', daily_rewards_view),
    path('daily-rewards/<int:day>/claim/', claim_daily_reward_view),
    path('leaderboard/', leaderboard_view),
]

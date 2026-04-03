from django.urls import path
from .controllers import streak_leaderboard_view, video_call_leaderboard_view, audio_call_leaderboard_view, total_call_leaderboard_view

urlpatterns = [
    path('streaks/', streak_leaderboard_view),
    path('video-call-time/', video_call_leaderboard_view),
    path('audio-call-time/', audio_call_leaderboard_view),
    path('total-call-time/', total_call_leaderboard_view),
    # Supporting matching the user's specific text too
    path('video-calls/', video_call_leaderboard_view),
    path('audio-calls/', audio_call_leaderboard_view),
]

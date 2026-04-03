from .controllers import (
    upload_streak, view_streaks, add_comment, list_comments, 
    get_streak_upload, view_streaks_snapchat, toggle_like, toggle_fire,
    toggle_user_fire, streak_leaderboard_view
)
from django.urls import path
urlpatterns = [
    path('', view_streaks),
    path('view/', view_streaks_snapchat),
    path('upload/', upload_streak),
    path('<int:upload_id>/', get_streak_upload),
    path('<int:upload_id>/comment/', add_comment),
    path('<int:upload_id>/comments/', list_comments),
    path('<int:upload_id>/like/', toggle_like),
    path('<int:upload_id>/fire/', toggle_fire),
    path('user/<int:user_id>/fire/', toggle_user_fire),
    path('leaderboard/', streak_leaderboard_view),
]

from api.modules.streaks.controllers import view_streaks, toggle_user_fire, streak_leaderboard_view, view_streak_view, \
    repost_streak_view, view_streaks_snapchat, upload_streak, get_streak_upload, toggle_like, list_comments, \
    add_comment, toggle_fire
from django.urls import path
urlpatterns = [
    path('', view_streaks),
    path('view/', view_streaks_snapchat, name='view-streaks-general'),
    path('upload/', upload_streak, name='upload-streak'),
    path('<int:upload_id>/', get_streak_upload, name='streak-detail'),
    path('<int:upload_id>/view/', view_streak_view, name='view-streak-unique'),
    path('<int:upload_id>/repost/', repost_streak_view, name='repost-streak'),
    path('<int:upload_id>/comment/', add_comment, name='streak-comment'),
    path('<int:upload_id>/comments/', list_comments, name='streak-comments-list'),
    path('<int:upload_id>/like/', toggle_like, name='streak-like'),
    path('<int:upload_id>/fire/', toggle_fire, name='streak-fire'),
    path('user/<int:user_id>/fire/', toggle_user_fire, name='user-fire'),
    path('leaderboard/', streak_leaderboard_view, name='streak-leaderboard'),
]

from django.urls import path
from .controllers import (
    list_stories_view, create_story_view, upload_story_media_view,
    view_story_view, list_story_views_view, like_story_view,
    comment_story_view, list_story_comments_view, delete_story_view, repost_story_view
)

urlpatterns = [
    path('', list_stories_view),
    path('create/', create_story_view),
    path('upload/', upload_story_media_view),
    path('<int:story_id>/', detail_story_view),
    path('<int:story_id>/view/', view_story_view),
    path('<int:story_id>/views/', list_story_views_view),
    path('<int:story_id>/like/', like_story_view),
    path('<int:story_id>/comment/', comment_story_view),
    path('<int:story_id>/comments/', list_story_comments_view), # Robust plural support
    path('<int:story_id>/repost/', repost_story_view),
    path('<int:story_id>/delete/', delete_story_view),
]

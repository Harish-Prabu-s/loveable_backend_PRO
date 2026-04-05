from django.urls import path
from .controllers import (
    feed_view, create_post_view, like_view, delete_post_view, comment_view,
    list_comments_view, share_post_view, repost_view, view_post_view,
)

urlpatterns = [
    path('feed/', feed_view),
    path('', create_post_view),
    path('<int:post_id>/view/', view_post_view, name='view-post'),
    path('<int:post_id>/like/', like_view),
    path('<int:post_id>/comment/', comment_view),
    path('<int:post_id>/comments/', list_comments_view), # GET: list, POST handled if needed or keep both
    # Robustness: ensure POST to either works
    path('<int:post_id>/comment/add/', comment_view),
    path('<int:post_id>/share/', share_post_view),
    path('<int:post_id>/repost/', repost_view),
    path('<int:post_id>/', delete_post_view),
]

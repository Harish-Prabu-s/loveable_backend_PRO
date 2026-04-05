from django.urls import path
from .controllers import (
    list_reels_view, create_reel_view, upload_reel_media_view,
    like_reel_view, comment_reel_view, list_comments_view,
    like_reel_view, comment_reel_view, list_comments_view,
    share_reel_view, delete_reel_view, repost_reel_view, detail_reel_view,
    view_reel_view
)

urlpatterns = [
    path('', list_reels_view),
    path('create/', create_reel_view),
    path('upload/', upload_reel_media_view),
    path('<int:pk>/', detail_reel_view),
    path('<int:pk>/view/', view_reel_view, name='view-reel'),
    path('<int:pk>/like/', like_reel_view),
    path('<int:pk>/comment/', comment_reel_view),
    path('<int:pk>/comments/', list_comments_view, name='list-reel-comments'),
    path('<int:pk>/share/', share_reel_view, name='share-reel'),
    path('<int:pk>/repost/', repost_reel_view, name='repost-reel'),
    path('<int:pk>/delete/', delete_reel_view, name='delete-reel'),
]

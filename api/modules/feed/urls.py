from django.urls import path
from . import controllers

urlpatterns = [
    path('',                              controllers.feed_view,        name='feed'),
    path('posts/<int:post_id>/view/',     controllers.record_post_view, name='feed-post-view'),
    path('reels/<int:reel_id>/view/',     controllers.record_reel_view, name='feed-reel-view'),
]

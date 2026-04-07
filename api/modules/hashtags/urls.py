from django.urls import path
from . import controllers

urlpatterns = [
    path('trending/', controllers.trending_hashtags, name='hashtags-trending'),
    path('search/', controllers.search_hashtags, name='hashtags-search'),
    path('<str:tag_name>/', controllers.hashtag_content, name='hashtag-content'),
]

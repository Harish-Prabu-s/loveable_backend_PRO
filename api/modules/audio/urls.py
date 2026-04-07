from django.urls import path
from .controllers import list_audios_view, trending_audios_view, search_audios_view

urlpatterns = [
    path('', list_audios_view, name='list_audios'),
    path('trending/', trending_audios_view, name='trending_audios'),
    path('search/', search_audios_view, name='search_audios'),
]

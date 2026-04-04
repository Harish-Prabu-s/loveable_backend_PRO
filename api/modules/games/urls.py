from django.urls import path
from .controllers import list_games_view, icebreaker_prompt_view, create_game_room_view, matchmake_view

urlpatterns = [
    path('', list_games_view),
    path('icebreaker/<str:kind>/', icebreaker_prompt_view),
    path('create/', create_game_room_view),
    path('matchmake/', matchmake_view),
]

from django.urls import path
from .controllers import (
    list_games_view, icebreaker_prompt_view, create_game_room_view, 
    matchmake_view, leave_matchmake_view, send_invite_view, respond_invite_view
)

urlpatterns = [
    path('', list_games_view),
    path('icebreaker/<str:kind>/', icebreaker_prompt_view),
    path('create-room/', create_game_room_view),
    path('matchmake/', matchmake_view),
    path('matchmake/leave/', leave_matchmake_view),
    path('invite/', send_invite_view),
    path('invite/respond/', respond_invite_view),
]

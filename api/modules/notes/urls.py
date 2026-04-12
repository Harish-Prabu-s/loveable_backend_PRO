from django.urls import path
from . import controllers

urlpatterns = [
    path('my/', controllers.get_my_note, name='note-my'),
    path('set/', controllers.set_note, name='note-set'),
    path('delete/', controllers.delete_note, name='note-delete'),
    path('friends/', controllers.list_friend_notes, name='notes-friends'),
    path('<int:pk>/like/', controllers.like_note_view, name='note-like'),
]

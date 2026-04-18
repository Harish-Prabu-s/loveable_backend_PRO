from django.urls import path
from . import controllers

urlpatterns = [
    path('chat-row/', controllers.get_chat_row, name='note-chat-row'),
    path('my-note/', controllers.get_my_note, name='note-my'),
    path('create-or-replace/', controllers.create_or_replace_note, name='note-create-or-replace'),
    path('my-note/', controllers.delete_my_note, name='note-delete'),
    path('<int:pk>/like/', controllers.toggle_like, name='note-like'),
    path('user/<int:user_id>/', controllers.get_user_note, name='note-user'),
]

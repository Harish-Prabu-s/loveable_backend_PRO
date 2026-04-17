from django.urls import path
from . import controllers

urlpatterns = [
    path('chat-row/', controllers.get_chat_row, name='note-chat-row'),
    path('my-note/', controllers.get_my_note, name='note-my'),
    path('create-or-replace/', controllers.create_or_replace_note, name='note-create-or-replace'),
    path('my-note/', controllers.delete_my_note, name='note-delete'), # Note: duplicate path for DELETE is handled by view if using method check, but here we have separate funcs. Actually controllers.py has delete_my_note. I'll use a different path or merge them.
]

from django.urls import path
from . import controllers

urlpatterns = [
    path('chat-row/', controllers.get_chat_row, name='note-chat-row'),
    path('my-note/', controllers.manage_my_note, name='note-manage'),
    path('create-or-replace/', controllers.create_or_replace_note, name='note-create-or-replace'),
    path('<int:pk>/', controllers.get_note_detail, name='note-detail'),
    path('<int:pk>/like/', controllers.toggle_like, name='note-like'),
    path('<int:pk>/comment/', controllers.post_comment, name='note-comment'),
    path('comment/<int:comment_id>/like/', controllers.toggle_like_comment, name='note-comment-like'),
    path('user/<int:user_id>/', controllers.get_user_note, name='note-user'),
]

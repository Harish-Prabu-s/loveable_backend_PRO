from django.urls import path
from .controllers import (
    users_overview_view,
    export_chat_images_pdf,
    export_voice_messages_pdf,
    export_stories_pdf,
    export_chat_conversation_pdf,
)

urlpatterns = [
    path('users/', users_overview_view),
    path('export/chat-images/<int:user_id>/', export_chat_images_pdf),
    path('export/voice-messages/<int:user_id>/', export_voice_messages_pdf),
    path('export/stories/<int:user_id>/', export_stories_pdf),
    path('export/chat-conversation/<int:user_id>/', export_chat_conversation_pdf),
]

from django.urls import path
from .controllers import (
    create_room_view, my_rooms_view, messages_view, send_message_view, 
    presence_view, start_call_view, end_call_view, contact_list_view,
    mark_seen_view, toggle_disappearing_view, update_theme_view
)

urlpatterns = [
    path('rooms/', my_rooms_view),
    path('rooms/create/', create_room_view),
    path('rooms/<int:room_id>/start_call/', start_call_view),
    path('rooms/<int:room_id>/end_call/', end_call_view),
    path('messages/<int:room_id>/', messages_view),
    path('messages/<int:room_id>/send/', send_message_view),
    path('presence/<int:user_id>/', presence_view),
    path('contact-list/', contact_list_view),
    path('rooms/<int:room_id>/toggle-disappearing/', toggle_disappearing_view),
    path('messages/<int:room_id>/mark-seen/', mark_seen_view),
    path('rooms/<int:room_id>/update_theme/', update_theme_view),
]

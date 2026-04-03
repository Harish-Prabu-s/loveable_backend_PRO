from django.urls import path
from .controllers import (
    list_notifications, mark_read, unread_count_view,
    send_follow_request_view, respond_follow_request_view, list_pending_follow_requests,
    register_push_token, screenshot_notification_view,
)

urlpatterns = [
    path('', list_notifications),
    path('read/', mark_read),
    path('unread-count/', unread_count_view),
    path('follow-requests/', list_pending_follow_requests),
    path('follow-request/<int:user_id>/', send_follow_request_view),
    path('follow-request/<int:request_id>/respond/', respond_follow_request_view),
    path('push-token/register/', register_push_token),
    path('screenshot/', screenshot_notification_view),
]

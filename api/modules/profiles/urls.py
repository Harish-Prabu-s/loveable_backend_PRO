from django.urls import path
from .controllers import (
    profile_me, profile_by_id, list_profiles_view, follow_view, unfollow_view, 
    send_friend_request_view, respond_friend_request_view,
    get_followers_view, get_following_view, share_profile_view,
    profile_insights_view, suggestion_profiles_view
)

urlpatterns = [
    path('me/', profile_me),
    path('me/insights/', profile_insights_view),
    path('suggestions/', suggestion_profiles_view),
    path('list/', list_profiles_view),
    path('<int:user_id>/', profile_by_id),
    path('<int:user_id>/follow/', follow_view, name='profile_follow'),
    path('<int:user_id>/unfollow/', unfollow_view, name='profile_unfollow'),
    path('<int:user_id>/followers/', get_followers_view),
    path('<int:user_id>/following/', get_following_view),
    path('<int:user_id>/friend-request/', send_friend_request_view, name='profile_send_friend_request'),
    path('friend-request/<int:request_id>/respond/', respond_friend_request_view, name='profile_respond_friend_request'),
    path('<int:user_id>/share/', share_profile_view, name='profile_share'),
]

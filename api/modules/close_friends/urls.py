from django.urls import path
from .controllers import add_close_friend, remove_close_friend, list_close_friends

urlpatterns = [
    path('add', add_close_friend),
    path('add/', add_close_friend),
    path('remove', remove_close_friend),
    path('remove/', remove_close_friend),
    path('list', list_close_friends),
    path('list/', list_close_friends),
]

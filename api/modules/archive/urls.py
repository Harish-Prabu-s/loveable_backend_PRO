from django.urls import path
from . import controllers

urlpatterns = [
    path('archive/', controllers.archive_view),
    path('unarchive/', controllers.unarchive_view),
    path('delete/', controllers.delete_view),
    path('list/', controllers.list_archived_view),
]

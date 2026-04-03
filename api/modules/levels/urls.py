from django.urls import path
from .controllers import my_level_view

urlpatterns = [
    path('', my_level_view),
]

from django.urls import path
from .controllers import list_audios_view

urlpatterns = [
    path('', list_audios_view, name='list_audios'),
]

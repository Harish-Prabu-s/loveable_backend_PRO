from django.urls import path
from .controllers import upload_file_view

urlpatterns = [
    path('', upload_file_view),
]

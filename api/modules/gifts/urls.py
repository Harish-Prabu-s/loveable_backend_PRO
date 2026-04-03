from django.urls import path
from .controllers import list_gifts, send_gift

urlpatterns = [
    path('', list_gifts),
    path('send/', send_gift),
]

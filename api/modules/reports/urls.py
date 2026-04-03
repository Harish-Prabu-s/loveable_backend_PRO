from django.urls import path
from . import controllers

urlpatterns = [
    path('create/', controllers.create_report),
]

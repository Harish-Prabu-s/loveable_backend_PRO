from django.urls import path
from . import controllers

urlpatterns = [
    path('initiate/', controllers.InitiateCallView.as_view()),
    path('accept/', controllers.AcceptCallView.as_view()),
    path('end/', controllers.EndCallView.as_view()),
    path('logs/', controllers.CallLogsView.as_view()),
    path('turn-credentials/', controllers.TurnCredentialsView.as_view()),
]

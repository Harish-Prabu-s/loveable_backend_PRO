from django.urls import path
from .controllers import list_offers_view, purchase_offer_view

urlpatterns = [
    path('', list_offers_view),
    path('purchase/', purchase_offer_view),
]

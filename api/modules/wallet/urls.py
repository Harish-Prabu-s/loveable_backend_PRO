from django.urls import path
from .controllers import wallet_view, transactions_view, purchase_view, spend_view, refund_view, transfer_view, earn_view, create_order_view, bulk_credit_view

urlpatterns = [
    path('', wallet_view),
    path('transactions/', transactions_view),
    path('create_order/', create_order_view),
    path('purchase/', purchase_view),
    path('spend/', spend_view),
    path('refund/', refund_view),
    path('earn/', earn_view),
    path('transfer/', transfer_view),
    path('seed-coins/', bulk_credit_view),   # Admin: add coins to all wallets
]

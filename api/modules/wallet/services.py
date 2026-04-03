from django.contrib.auth.models import User
from ...models import Wallet, CoinTransaction
from ..auth.services import create_tokens

def get_wallet(user: User):
    return user.wallet

def list_transactions(user: User, limit: int = 50):
    w = user.wallet
    return w.transactions.order_by('-created_at')[:limit]

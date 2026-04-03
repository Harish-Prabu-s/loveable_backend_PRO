from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import F
from ...serializers import GiftSerializer
from ...models import Gift, GiftTransaction, Wallet, CoinTransaction
from django.contrib.auth.models import User

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_gifts(request):
    gifts = Gift.objects.all()
    # If no gifts, create some default ones
    if not gifts.exists():
        defaults = [
            {'name': 'Rose', 'icon': '🌹', 'cost': 10},
            {'name': 'Heart', 'icon': '❤️', 'cost': 50},
            {'name': 'Chocolate', 'icon': '🍫', 'cost': 100},
            {'name': 'Diamond', 'icon': '💎', 'cost': 500},
            {'name': 'Crown', 'icon': '👑', 'cost': 1000},
            {'name': 'Car', 'icon': '🏎️', 'cost': 5000},
        ]
        for d in defaults:
            Gift.objects.create(**d)
        gifts = Gift.objects.all()
    
    return Response(GiftSerializer(gifts, many=True).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_gift(request):
    gift_id = request.data.get('gift_id')
    receiver_id = request.data.get('receiver_id')
    
    if not gift_id or not receiver_id:
        return Response({'error': 'gift_id and receiver_id required'}, status=400)
    
    try:
        gift = Gift.objects.get(id=gift_id)
        receiver = User.objects.get(id=receiver_id)
    except (Gift.DoesNotExist, User.DoesNotExist):
        return Response({'error': 'Invalid gift or user'}, status=404)
        
    sender_wallet = Wallet.objects.get(user=request.user)
    if sender_wallet.coin_balance < gift.cost:
        return Response({'error': 'Insufficient coins'}, status=400)
        
    # Transaction
    # 1. Deduct from Sender
    sender_wallet.coin_balance = F('coin_balance') - gift.cost
    sender_wallet.total_spent = F('total_spent') + gift.cost
    sender_wallet.save(update_fields=['coin_balance', 'total_spent'])
    sender_wallet.refresh_from_db()
    
    CoinTransaction.objects.create(
        wallet=sender_wallet,
        type='debit',
        transaction_type='gift_sent',
        amount=gift.cost,
        description=f'Sent {gift.name} to {receiver.username}'
    )
    
    # 2. Add to Receiver (100% value converted to coins)
    receiver_amount = gift.cost
    receiver_wallet, _ = Wallet.objects.get_or_create(user=receiver)
    receiver_wallet.coin_balance = F('coin_balance') + receiver_amount
    receiver_wallet.total_earned = F('total_earned') + receiver_amount
    receiver_wallet.save(update_fields=['coin_balance', 'total_earned'])
    
    CoinTransaction.objects.create(
        wallet=receiver_wallet,
        type='credit',
        transaction_type='gift_received',
        amount=receiver_amount,
        description=f'Received {gift.name} from {request.user.username}'
    )
    
    # 3. Record Gift Transaction
    GiftTransaction.objects.create(
        sender=request.user,
        receiver=receiver,
        gift=gift
    )
    
    return Response({'success': True, 'message': f'Sent {gift.name}!', 'new_balance': sender_wallet.coin_balance})

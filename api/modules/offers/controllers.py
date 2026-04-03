from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import F
from ...serializers import OfferSerializer
from .services import list_active_offers
from ...models import Offer, Wallet, CoinTransaction, Payment

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_offers_view(request):
    qs = list_active_offers()
    return Response(OfferSerializer(qs, many=True).data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_offer_view(request):
    offer_id = request.data.get('offer_id')
    if not offer_id:
        return Response({'error': 'offer_id required'}, status=400)
    
    try:
        offer = Offer.objects.get(pk=offer_id, is_active=True)
    except Offer.DoesNotExist:
        return Response({'error': 'Offer not found or inactive'}, status=404)
        
    if offer.offer_type != 'coin_package':
        return Response({'error': 'This offer is not a coin package'}, status=400)
    
    # Simulate payment completion
    amount = offer.price
    coins = offer.coins_awarded
    
    order_id = f"OFFER_{offer.id}_{request.user.id}"
    
    payment = Payment.objects.create(
        user=request.user,
        amount=amount,
        currency=offer.currency,
        razorpay_order_id=order_id,
        status='completed',
        coins_added=coins
    )
    
    w, _ = Wallet.objects.get_or_create(user=request.user)
    w.coin_balance = F('coin_balance') + coins
    w.total_earned = F('total_earned') + coins
    w.save(update_fields=['coin_balance', 'total_earned'])
    
    CoinTransaction.objects.create(
        wallet=w, 
        type='credit', 
        transaction_type='purchase', 
        amount=coins, 
        description=f'Purchased Package: {offer.title}'
    )
    
    return Response({'success': True, 'payment_id': payment.id})

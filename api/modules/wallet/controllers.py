from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import F
from ...serializers import WalletSerializer, CoinTransactionSerializer
from .services import get_wallet, list_transactions
from ...models import Payment, Wallet, CoinTransaction
from django.contrib.auth.models import User
from django.conf import settings
import razorpay

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def wallet_view(request):
    w = get_wallet(request.user)
    return Response(WalletSerializer(w).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transactions_view(request):
    qs = list_transactions(request.user)
    return Response({
        'count': qs.count(),
        'next': None,
        'previous': None,
        'results': CoinTransactionSerializer(qs, many=True).data
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_order_view(request):
    amount = float(request.data.get('amount', 0))
    currency = request.data.get('currency', 'INR')
    
    if amount <= 0:
        return Response({'error': 'amount required'}, status=400)
    
    # Initialize Razorpay Client
    if hasattr(settings, 'RAZORPAY_KEY_ID') and settings.RAZORPAY_KEY_ID:
        try:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
            # Create Order (amount in paise)
            order_data = {
                'amount': int(amount * 100),
                'currency': currency,
                'payment_capture': 1,
                'notes': {
                    'user_id': request.user.id,
                    'user_phone': request.user.profile.phone_number
                }
            }
            order = client.order.create(data=order_data)
            print(f"Razorpay Order Created: {order['id']}")
            return Response({'success': True, 'order_id': order['id'], 'key_id': settings.RAZORPAY_KEY_ID})
        except Exception as e:
            print(f"Razorpay Create Order Error: {e}")
            return Response({'error': 'Razorpay Error', 'details': str(e)}, status=500)
    else:
        print("Razorpay Error: Keys not configured")
        return Response({'error': 'Razorpay not configured'}, status=500)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def purchase_view(request):
    amount = float(request.data.get('amount', 0))
    coins = int(request.data.get('coins', 0))
    razorpay_payment_id = request.data.get('razorpay_payment_id')
    razorpay_order_id = request.data.get('razorpay_order_id')
    razorpay_signature = request.data.get('razorpay_signature')

    if amount <= 0 or coins <= 0:
        return Response({'error': 'amount and coins required'}, status=400)
    
    # Check if this is a Mock payment (from our frontend testing tool)
    is_mock = razorpay_payment_id and razorpay_payment_id.startswith('pay_mock_')
    
    # Initialize Razorpay Client if not mock and keys exist
    client = None
    if not is_mock:
        if hasattr(settings, 'RAZORPAY_KEY_ID') and settings.RAZORPAY_KEY_ID:
            client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))
        else:
            print("Razorpay Error: Keys not configured on backend")
            return Response({'error': 'Razorpay configuration missing'}, status=500)

    # Verify Signature if it's a real payment attempt
    if not is_mock:
        if not (razorpay_payment_id and razorpay_order_id and razorpay_signature):
             print(f"Razorpay Error: Missing verification parameters. Order: {razorpay_order_id}, Payment: {razorpay_payment_id}, Sig: {razorpay_signature}")
             return Response({'error': 'Payment verification incomplete'}, status=400)

        try:
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            print(f"Verifying Razorpay Signature with params: {params}")
            client.utility.verify_payment_signature(params)
            print(f"Razorpay Payment Verified: {razorpay_payment_id}")
        except razorpay.errors.SignatureVerificationError as e:
            print(f"Razorpay Signature Verification Failed: {e}")
            print(f"Params: {params}")
            return Response({'error': 'Payment verification failed'}, status=400)
        except Exception as e:
            print(f"Razorpay General Error: {e}")
            return Response({'error': 'Payment processing error'}, status=500)
    
    # Create or Update Payment Record
    # If order_id was provided, we might have created a pending payment earlier (not implemented here but good practice)
    # For now, we create a new completed payment record
    
    payment = Payment.objects.create(
        user=request.user,
        amount=amount,
        currency='INR',
        razorpay_order_id=razorpay_order_id or f"ORDER_{request.user.id}_{coins}",
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
        status='completed',
        coins_added=coins
    )
    
    w = Wallet.objects.get(user=request.user)
    w.coin_balance = F('coin_balance') + coins
    w.total_earned = F('total_earned') + coins
    w.save(update_fields=['coin_balance', 'total_earned'])
    
    CoinTransaction.objects.create(
        wallet=w, 
        type='credit', 
        transaction_type='purchase', 
        amount=coins, 
        description=f'Purchase via {razorpay_payment_id or "Direct"}'
    )
    
    return Response({'success': True, 'payment_id': payment.id})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def spend_view(request):
    amount = int(request.data.get('amount', 0))
    description = request.data.get('description', 'Spent')
    if amount <= 0:
        return Response({'error': 'amount required'}, status=400)
    
    w = Wallet.objects.get(user=request.user)
    if w.coin_balance < amount:
        return Response({'error': 'Insufficient funds'}, status=400)
        
    w.coin_balance = F('coin_balance') - amount
    w.total_spent = F('total_spent') + amount
    w.save(update_fields=['coin_balance', 'total_spent'])
    w.refresh_from_db()
    CoinTransaction.objects.create(wallet=w, type='debit', transaction_type='spent', amount=amount, description=description)
    return Response({'success': True, 'new_balance': w.coin_balance})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def refund_view(request):
    amount = int(request.data.get('amount', 0))
    description = request.data.get('description', 'Refund')
    if amount <= 0:
        return Response({'error': 'amount required'}, status=400)
    
    w = Wallet.objects.get(user=request.user)
    w.coin_balance = F('coin_balance') + amount
    # Do not increase total_earned for refunds, as it's not "earned"
    w.save(update_fields=['coin_balance'])
    w.refresh_from_db()
    CoinTransaction.objects.create(wallet=w, type='credit', transaction_type='refund', amount=amount, description=description)
    return Response({'success': True, 'new_balance': w.coin_balance})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def earn_view(request):
    amount = int(request.data.get('amount', 0))
    description = request.data.get('description', 'Earned')
    if amount <= 0:
        return Response({'error': 'amount required'}, status=400)
    
    w = Wallet.objects.get(user=request.user)
    w.coin_balance = F('coin_balance') + amount
    w.total_earned = F('total_earned') + amount
    w.save(update_fields=['coin_balance', 'total_earned'])
    w.refresh_from_db()
    CoinTransaction.objects.create(wallet=w, type='credit', transaction_type='earned', amount=amount, description=description)
    return Response({'success': True, 'new_balance': w.coin_balance})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def transfer_view(request):
    amount = int(request.data.get('amount', 0))
    receiver_id = request.data.get('receiver_id')
    description = request.data.get('description', 'Transfer')
    
    if amount <= 0 or not receiver_id:
        return Response({'error': 'amount and receiver_id required'}, status=400)
    
    try:
        receiver = User.objects.get(id=receiver_id)
    except User.DoesNotExist:
        return Response({'error': 'Receiver not found'}, status=404)
        
    sender_wallet = Wallet.objects.get(user=request.user)
    if sender_wallet.coin_balance < amount:
        return Response({'error': 'Insufficient funds'}, status=400)
        
    # 1. Deduct from Sender
    sender_wallet.coin_balance = F('coin_balance') - amount
    sender_wallet.total_spent = F('total_spent') + amount
    sender_wallet.save(update_fields=['coin_balance', 'total_spent'])
    sender_wallet.refresh_from_db()
    
    CoinTransaction.objects.create(
        wallet=sender_wallet,
        type='debit',
        transaction_type='transfer_sent',
        amount=amount,
        description=f'{description} to {receiver.username}'
    )
    
    # 2. Add to Receiver
    receiver_wallet, _ = Wallet.objects.get_or_create(user=receiver)
    receiver_wallet.coin_balance = F('coin_balance') + amount
    receiver_wallet.total_earned = F('total_earned') + amount
    receiver_wallet.save(update_fields=['coin_balance', 'total_earned'])
    
    CoinTransaction.objects.create(
        wallet=receiver_wallet,
        type='credit',
        transaction_type='transfer_received',
        amount=amount,
        description=f'{description} from {request.user.username}'
    )
    
    return Response({'success': True, 'new_balance': sender_wallet.coin_balance})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_credit_view(request):
    """
    POST /api/wallet/seed-coins/
    Admin-only: Adds 'coins' to every user's wallet instantly.
    Useful for testing calls without going through payment.

    Body: { "coins": 1000, "description": "Test credit" }  (optional fields)
    """
    if not request.user.is_staff:
        return Response({'error': 'Admin only.'}, status=403)

    coins = int(request.data.get('coins', 500))
    description = request.data.get('description', 'Admin seed credit')

    if coins <= 0:
        return Response({'error': 'coins must be > 0'}, status=400)

    wallets = Wallet.objects.all()
    updated = 0
    for w in wallets:
        w.coin_balance = F('coin_balance') + coins
        w.total_earned = F('total_earned') + coins
        w.save(update_fields=['coin_balance', 'total_earned'])
        CoinTransaction.objects.create(
            wallet=w,
            type='credit',
            transaction_type='earned',
            amount=coins,
            description=description
        )
        updated += 1

    return Response({
        'success': True,
        'wallets_updated': updated,
        'coins_added_each': coins,
        'message': f'Added {coins} coins to {updated} user wallets.'
    })
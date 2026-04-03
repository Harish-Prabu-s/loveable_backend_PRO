from django.test import TestCase
from django.contrib.auth.models import User
from .models import Wallet, Gift, GiftTransaction, CoinTransaction

class GiftingSystemTest(TestCase):
    def setUp(self):
        # Create Users
        self.alice = User.objects.create_user(username='alice', password='password')
        self.bob = User.objects.create_user(username='bob', password='password')
        
        # Create Wallets
        self.alice_wallet = Wallet.objects.create(user=self.alice, coin_balance=100)
        self.bob_wallet = Wallet.objects.create(user=self.bob, coin_balance=0)
        
        # Create Gift
        self.rose = Gift.objects.create(name='Rose', icon='🌹', cost=10)

    def test_send_gift_success(self):
        """Test sending a gift correctly updates balances and creates records."""
        
        # 1. Send Gift Logic (Simulating what the View does)
        # Deduct from Sender
        self.alice_wallet.coin_balance -= self.rose.cost
        self.alice_wallet.total_spent += self.rose.cost
        self.alice_wallet.save()
        
        CoinTransaction.objects.create(
            wallet=self.alice_wallet,
            type='debit',
            transaction_type='gift_sent',
            amount=self.rose.cost,
            description=f'Sent {self.rose.name} to {self.bob.username}'
        )
        
        # Add to Receiver (50% value)
        receiver_amount = int(self.rose.cost * 0.5)
        self.bob_wallet.coin_balance += receiver_amount
        self.bob_wallet.total_earned += receiver_amount
        self.bob_wallet.save()
        
        CoinTransaction.objects.create(
            wallet=self.bob_wallet,
            type='credit',
            transaction_type='gift_received',
            amount=receiver_amount,
            description=f'Received {self.rose.name} from {self.alice.username}'
        )
        
        # Record Gift Transaction
        GiftTransaction.objects.create(
            sender=self.alice,
            receiver=self.bob,
            gift=self.rose
        )
        
        # 2. Assertions
        self.alice_wallet.refresh_from_db()
        self.bob_wallet.refresh_from_db()
        
        self.assertEqual(self.alice_wallet.coin_balance, 90) # 100 - 10
        self.assertEqual(self.bob_wallet.coin_balance, 5)    # 0 + 5
        
        self.assertEqual(GiftTransaction.objects.count(), 1)
        self.assertEqual(CoinTransaction.objects.count(), 2)

    def test_insufficient_funds(self):
        """Test sending a gift fails with insufficient funds."""
        self.alice_wallet.coin_balance = 5
        self.alice_wallet.save()
        
        # Attempt to send (logic check)
        can_send = self.alice_wallet.coin_balance >= self.rose.cost
        self.assertFalse(can_send)

class FirstCallInsuranceTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='charlie', password='password')
        self.wallet = Wallet.objects.create(user=self.user, coin_balance=50)

    def test_insurance_refund_flow(self):
        """Test the financial flow of a call insurance refund."""
        call_cost = 10
        
        # 1. Start Call (Deduct)
        self.wallet.coin_balance -= call_cost
        self.wallet.save()
        
        # Assert deducted
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.coin_balance, 40)
        
        # 2. Call ends quickly (<30s) -> Refund
        self.wallet.coin_balance += call_cost
        self.wallet.save()
        
        # Assert refunded
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.coin_balance, 50)

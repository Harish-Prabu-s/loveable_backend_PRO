from decimal import Decimal
from django.utils import timezone
from api.models import BetMatch, Wallet, LeagueStats, CoinTransaction
from api.modules.monetization.services import get_rewards


def _get_profile(user):
    try:
        return user.profile
    except Exception:
        return None


def create_bet_match(requesting_user) -> BetMatch:
    """Creates a pending BetMatch.  Requester must be Male."""
    profile = _get_profile(requesting_user)
    if not profile:
        raise ValueError('Profile not found.')

    gender = profile.gender
    if gender not in ('M', 'F'):
        raise ValueError('Gender must be set to Male or Female to join Bet Match.')

    if gender == 'M':
        match = BetMatch.objects.create(male_user=requesting_user)
    else:
        # Female: find a pending match without a female player
        existing = BetMatch.objects.filter(status='pending', female_user__isnull=True).first()
        if existing:
            existing.female_user = requesting_user
            existing.status = 'active'
            existing.save(update_fields=['female_user', 'status'])
            return existing
        raise ValueError('No pending Bet Match available. Please wait for a male user to create one.')

    return match


def join_bet_match(match_id: int, requesting_user) -> BetMatch:
    """Female user joins existing pending match."""
    try:
        match = BetMatch.objects.get(pk=match_id, status='pending', female_user__isnull=True)
    except BetMatch.DoesNotExist:
        raise ValueError('Match not found or already filled.')

    profile = _get_profile(requesting_user)
    if not profile or profile.gender != 'F':
        raise ValueError('Only Female users can join an existing Bet Match.')

    if match.male_user == requesting_user:
        raise ValueError('Cannot join your own match.')

    match.female_user = requesting_user
    match.status = 'active'
    match.save(update_fields=['female_user', 'status'])
    return match


def declare_result(match_id: int, winner_gender: str) -> BetMatch:
    """Declare winner and distribute rewards."""
    if winner_gender not in ('M', 'F'):
        raise ValueError("winner_gender must be 'M' or 'F'.")

    try:
        match = BetMatch.objects.get(pk=match_id, status='active')
    except BetMatch.DoesNotExist:
        raise ValueError('Active match not found.')

    reward_coins, reward_money = get_rewards('bet_match')

    match.winner_gender = winner_gender
    match.status = 'completed'
    match.ended_at = timezone.now()
    match.result_coins = reward_coins if winner_gender == 'M' else 0
    match.result_money = reward_money if winner_gender == 'F' else Decimal('0.00')
    match.save()

    # Distribute rewards
    if winner_gender == 'M' and reward_coins > 0:
        wallet, _ = Wallet.objects.get_or_create(user=match.male_user)
        wallet.coin_balance += reward_coins
        wallet.total_earned += reward_coins
        wallet.save(update_fields=['coin_balance', 'total_earned', 'updated_at'])
        CoinTransaction.objects.create(
            wallet=wallet, type='credit', transaction_type='earned',
            amount=reward_coins, description='Bet Match win reward'
        )
        # Update league stats for male winner
        stats, _ = LeagueStats.objects.get_or_create(user=match.male_user)
        stats.bet_match_wins += 1
        stats.total_coins_earned += reward_coins
        stats.save(update_fields=['bet_match_wins', 'total_coins_earned', 'updated_at'])

    elif winner_gender == 'F' and reward_money > 0:
        wallet, _ = Wallet.objects.get_or_create(user=match.female_user)
        wallet.money_balance += reward_money
        wallet.save(update_fields=['money_balance', 'updated_at'])
        # Update league stats for female winner
        stats, _ = LeagueStats.objects.get_or_create(user=match.female_user)
        stats.bet_match_wins += 1
        stats.total_money_earned += reward_money
        stats.save(update_fields=['bet_match_wins', 'total_money_earned', 'updated_at'])

    return match

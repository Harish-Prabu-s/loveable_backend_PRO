from django.contrib.auth.models import User
from django.db.models import F
from ...models import LevelProgress, DailyReward, Badge
from ...models import Wallet, CoinTransaction
from django.utils import timezone

def get_user_level(user: User) -> LevelProgress:
    lp, _ = LevelProgress.objects.get_or_create(user=user)
    return lp

def list_daily_rewards(user: User):
    rewards = DailyReward.objects.filter(user=user).order_by('day')
    if not rewards.exists():
        bulk = []
        for day in range(1, 8):
            bulk.append(DailyReward(user=user, day=day, xp_reward=100, coin_reward=10))
        DailyReward.objects.bulk_create(bulk)
        rewards = DailyReward.objects.filter(user=user).order_by('day')
    return rewards

def claim_daily_reward(user: User, day: int):
    dr = DailyReward.objects.filter(user=user, day=day).first()
    if not dr:
        return None
    if dr.claimed_at:
        return dr
    dr.claimed_at = timezone.now()
    dr.streak = (DailyReward.objects.filter(user=user, claimed_at__isnull=False).count() + 1)
    dr.save()
    w = Wallet.objects.get(user=user)
    w.coin_balance = F('coin_balance') + dr.coin_reward
    w.total_earned = F('total_earned') + dr.coin_reward
    w.save(update_fields=['coin_balance', 'total_earned'])
    CoinTransaction.objects.create(wallet=w, type='credit', transaction_type='earned', amount=dr.coin_reward, description=f'Daily reward day {day}')
    lp = get_user_level(user)
    lp.xp += dr.xp_reward
    # Simple leveling: 1000 xp per level
    lp.level = max(lp.level, (lp.xp // 1000) + 1)
    lp.save()
    return dr

def leaderboard(limit: int = 50):
    return LevelProgress.objects.select_related('user').order_by('-xp')[:limit]

from django.db.models import Sum, Max, Q, Count, Case, When, IntegerField, F
from django.db.models.functions import Greatest

def get_streak_leaderboard_service(limit: int = 50):
    """
    Optimized: Get top users by their highest streak in a single query.
    """
    # We find the maximum streak_count for each user, considering they could be user1 or user2.
    # We use a combined approach with annotate.
    return User.objects.filter(is_active=True).annotate(
        max_streak_u1=Max('streaks_user1__streak_count'),
        max_streak_u2=Max('streaks_user2__streak_count')
    ).annotate(
        streak_count=Greatest(
            F('max_streak_u1'), 
            F('max_streak_u2'),
            default=0,
            output_field=IntegerField()
        )
    ).filter(streak_count__gt=0).select_related('profile').order_by('-streak_count')[:limit]

def get_call_time_leaderboard_service(call_type: str, limit: int = 50, month: int = None, year: int = None):
    """
    Optimized: Get top users by total call duration in a single query.
    Filters by current month if month/year are provided.
    """
    # Current month filtering as requested
    now = timezone.now()
    month = month or now.month
    year = year or now.year

    call_q = Q(duration_seconds__gt=0, started_at__month=month, started_at__year=year)
    if call_type.upper() != 'ALL':
        call_q &= Q(call_type=call_type.upper())

    # Sum duration from both calls_made and calls_received roles.
    # Note: We filter the specific relations calls_made and calls_received with the monthly constraints.
    q_made = call_q
    q_received = call_q

    return User.objects.filter(is_active=True).annotate(
        total_made=Sum('calls_made__duration_seconds', filter=q_made),
        total_received=Sum('calls_received__duration_seconds', filter=q_received),
        # Breakdown by type if ALL
        total_made_video=Sum('calls_made__duration_seconds', filter=q_made & Q(calls_made__call_type='VIDEO')),
        total_received_video=Sum('calls_received__duration_seconds', filter=q_received & Q(calls_received__call_type='VIDEO')),
        total_made_voice=Sum('calls_made__duration_seconds', filter=q_made & Q(calls_made__call_type='VOICE')),
        total_received_voice=Sum('calls_received__duration_seconds', filter=q_received & Q(calls_received__call_type='VOICE')),
    ).annotate(
        total_duration=Case(
            When(total_made__isnull=False, total_received__isnull=False, then=F('total_made') + F('total_received')),
            When(total_made__isnull=False, then=F('total_made')),
            When(total_received__isnull=False, then=F('total_received')),
            default=0,
            output_field=IntegerField()
        )
    ).filter(total_duration__gt=0).select_related('profile').order_by('-total_duration')[:limit]

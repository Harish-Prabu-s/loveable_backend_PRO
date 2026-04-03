from decimal import Decimal
from django.utils import timezone
from api.models import MonetizationRule


# Default pricing if no DB rules exist yet
DEFAULTS = {
    'audio_call':  {'cost_per_minute': 10, 'night': 30},
    'video_call':  {'cost_per_minute': 30, 'night': 60},
    'live':        {'cost_per_minute': 100, 'night': 120},
    'chat':        {'cost_per_message': 1, 'night': 1},
    'photo':       {'cost_per_media': 5, 'night': 5},
    'video_msg':   {'cost_per_media': 10, 'night': 10},
    'voice_msg':   {'cost_per_media': 5, 'night': 5},
    'bet_match':   {'cost_per_minute': 0, 'night': 0},
    'gift':        {'cost_per_media': 0, 'night': 0},
}

NIGHT_START = 22  # 10 PM
NIGHT_END   = 4   # 4 AM


def is_night_time():
    hour = timezone.localtime(timezone.now()).hour
    return hour >= NIGHT_START or hour < NIGHT_END


def get_rule(action_type: str) -> MonetizationRule | None:
    try:
        return MonetizationRule.objects.get(action_type=action_type, is_active=True)
    except MonetizationRule.DoesNotExist:
        return None


def get_cost(action_type: str, field: str) -> int:
    """Fetch cost from DB rule; fall back to hardcoded defaults."""
    rule = get_rule(action_type)
    night = is_night_time()

    if rule:
        base = getattr(rule, field, 0)
        if night:
            base = int(Decimal(str(base)) * rule.night_cost_multiplier)
        return base

    # Fallback
    d = DEFAULTS.get(action_type, {})
    return d.get('night' if night else field, d.get(field, 0))


def get_call_cost_per_min(call_type: str) -> int:
    """Return coin cost per minute for a call type ('audio_call' or 'video_call')."""
    return get_cost(call_type, 'cost_per_minute')


def get_chat_cost() -> int:
    return get_cost('chat', 'cost_per_message')


def get_media_cost(media_type: str) -> int:
    """media_type: 'photo' or 'video_msg'"""
    return get_cost(media_type, 'cost_per_media')


def get_rewards(action_type: str):
    """Returns (reward_male_coins, reward_female_money)."""
    rule = get_rule(action_type)
    if rule:
        return rule.reward_male, rule.reward_female
    return 0, Decimal('0.00')


def seed_default_rules():
    """Create default MonetizationRule rows if they don't exist yet."""
    defaults_full = [
        dict(action_type='audio_call', cost_per_minute=10,  cost_per_message=0,  cost_per_media=0,  night_cost_multiplier='3.00', reward_male=0, reward_female='0.00'),
        dict(action_type='video_call', cost_per_minute=30,  cost_per_message=0,  cost_per_media=0,  night_cost_multiplier='2.00', reward_male=0, reward_female='0.00'),
        dict(action_type='live',       cost_per_minute=100, cost_per_message=0,  cost_per_media=0,  night_cost_multiplier='1.20', reward_male=0, reward_female='0.00'),
        dict(action_type='chat',       cost_per_minute=0,   cost_per_message=1,  cost_per_media=0,  night_cost_multiplier='2.00', reward_male=0, reward_female='0.00'),
        dict(action_type='photo',      cost_per_minute=0,   cost_per_message=0,  cost_per_media=10, night_cost_multiplier='2.00', reward_male=0, reward_female='0.00'),
        dict(action_type='video_msg',  cost_per_minute=0,   cost_per_message=0,  cost_per_media=30, night_cost_multiplier='1.33', reward_male=0, reward_female='0.00'),
        dict(action_type='bet_match',  cost_per_minute=0,   cost_per_message=0,  cost_per_media=50, night_cost_multiplier='1.00', reward_male=100, reward_female='50.00'),
        dict(action_type='gift',       cost_per_minute=0,   cost_per_message=0,  cost_per_media=0,  night_cost_multiplier='1.00', reward_male=0, reward_female='0.00'),
    ]
    for rule_data in defaults_full:
        MonetizationRule.objects.get_or_create(
            action_type=rule_data['action_type'],
            defaults=rule_data,
        )

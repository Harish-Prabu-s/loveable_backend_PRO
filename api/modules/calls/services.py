from decimal import Decimal
from django.utils import timezone
from api.models import CallSession, Wallet, LeagueStats, UserSetting
from api.modules.monetization.services import get_call_cost_per_min
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def can_receive_call(user, call_type: str) -> tuple[bool, str]:
    """Check female safety settings before initiating a call."""
    try:
        settings = user.settings
        pref = settings.call_preference  # 'both', 'audio', 'video'
        if pref == 'audio' and call_type == 'VIDEO':
            return False, 'This user only accepts audio calls.'
        if pref == 'video' and call_type == 'VOICE':
            return False, 'This user only accepts video calls.'
    except Exception:
        pass
    return True, ''


def initiate_call(caller, callee, call_type: str, room_id: str = None) -> CallSession:
    """Create a new call session.  Validates safety settings."""
    allowed, reason = can_receive_call(callee, call_type)
    if not allowed:
        raise PermissionError(reason)

    coins_per_min = get_call_cost_per_min(
        'audio_call' if call_type == 'VOICE' else 'video_call'
    )
    session = CallSession.objects.create(
        caller=caller,
        callee=callee,
        call_type=call_type,
        room_id=room_id,
        coins_per_min=coins_per_min,
        started_at=timezone.now(),
    )
    # Mark callee as busy
    callee.profile.is_busy = True
    callee.profile.save(update_fields=['is_busy'])

    # Notify callee via WebSocket (Call Channel)
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'call_{callee.id}',
        {
            'type': 'incoming_call',
            'content': {
                'type': 'incoming-call',
                'sessionId': session.id,
                'roomId': session.room_id,
                'callerName': caller.profile.display_name if hasattr(caller, 'profile') else 'User',
                'callerPhoto': caller.profile.photo.url if hasattr(caller, 'profile') and caller.profile.photo else None,
                'callType': 'video' if call_type == 'VIDEO' else 'audio',
                'callerId': caller.id
            }
        }
    )

    # Notify callee via Push Notification (for background/killed state)
    try:
        from api.modules.notifications.push_service import send_call_push_notification
        send_call_push_notification(
            caller_name=caller.profile.display_name if hasattr(caller, 'profile') else 'User',
            callee_id=callee.id,
            session_id=session.id,
            call_type='video' if call_type == 'VIDEO' else 'audio'
        )
    except Exception as e:
        print(f"AG_PUSH_DEBUG: Failed to send call push notification: {e}")

    return session


def accept_call(session: CallSession) -> CallSession:
    """Mark a call session as active when the callee accepts."""
    session.started_at = timezone.now()
    session.save(update_fields=['started_at'])
    return session


def end_call(session: CallSession) -> dict:
    """End a call session, compute coins, deduct from caller wallet, update league stats."""
    if session.ended_at:
        return {'detail': 'Already ended.'}

    now = timezone.now()
    session.ended_at = now
    duration_s = int((now - session.started_at).total_seconds())
    session.duration_seconds = duration_s

    # Compute coin cost (per minute, rounded up)
    minutes = max(1, (duration_s + 59) // 60)
    coins_spent = minutes * session.coins_per_min
    session.coins_spent = coins_spent
    session.save()

    # Deduct coins from caller
    try:
        wallet = session.caller.wallet
        wallet.coin_balance = max(0, wallet.coin_balance - coins_spent)
        wallet.total_spent += coins_spent
        wallet.save(update_fields=['coin_balance', 'total_spent', 'updated_at'])
    except Wallet.DoesNotExist:
        pass

    # Update league stats for callee (calls received)
    stats, _ = LeagueStats.objects.get_or_create(user=session.callee)
    stats.total_calls_received += 1
    stats.total_call_seconds += duration_s
    if duration_s > stats.longest_call_seconds:
        stats.longest_call_seconds = duration_s
    stats.save(update_fields=['total_calls_received', 'total_call_seconds', 'longest_call_seconds', 'updated_at'])

    # Mark callee as not busy
    session.callee.profile.is_busy = False
    session.callee.profile.save(update_fields=['is_busy'])

    return {
        'duration_seconds': duration_s,
        'coins_spent': coins_spent,
    }

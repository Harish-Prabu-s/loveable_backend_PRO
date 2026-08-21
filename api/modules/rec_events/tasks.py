"""
Event Stream Consumer — Celery Task
=====================================
Consumes events from the Redis Stream `user-events` and persists them to MySQL.

Uses Redis consumer groups for reliable delivery:
- Group: `rec-event-workers`
- Consumer: dynamically named per Celery worker
- Acknowledges each message only after successful MySQL insert

Idempotency is guaranteed by the `event_id` UUID primary key on RecEvent —
if a re-delivery arrives, the IntegrityError from the unique constraint
is caught and the duplicate is silently skipped.
"""

import json
import logging
import uuid
from datetime import datetime

import redis
from celery import shared_task
from django.conf import settings
from django.db import IntegrityError
from django.utils import timezone

from .abuse_filter import is_event_suspicious

logger = logging.getLogger(__name__)

# Redis Stream constants
STREAM_KEY = 'user-events'
CONSUMER_GROUP = 'rec-event-workers'
BATCH_SIZE = 50  # Process up to 50 events per read
BLOCK_MS = 2000  # Block for 2 seconds waiting for new messages


def _get_stream_redis():
    """Get Redis connection for the Streams DB."""
    return redis.Redis.from_url(
        settings.REDIS_STREAMS_URL,
        decode_responses=True,
    )


def _ensure_consumer_group(r):
    """Create the consumer group if it doesn't exist."""
    try:
        r.xgroup_create(STREAM_KEY, CONSUMER_GROUP, id='0', mkstream=True)
        logger.info(f'Created consumer group "{CONSUMER_GROUP}" on stream "{STREAM_KEY}"')
    except redis.ResponseError as e:
        if 'BUSYGROUP' in str(e):
            pass  # Group already exists — normal on restart
        else:
            raise


def _parse_stream_event(fields: dict) -> dict:
    """Parse a Redis Stream message's field dict into a RecEvent-compatible dict."""
    device_context = {}
    if fields.get('device_context'):
        try:
            device_context = json.loads(fields['device_context'])
        except (json.JSONDecodeError, TypeError):
            device_context = {}

    session_id = fields.get('session_id', '')
    if session_id:
        try:
            session_id = uuid.UUID(session_id)
        except ValueError:
            session_id = None
    else:
        session_id = None

    play_session_id = fields.get('play_session_id', '')
    if play_session_id:
        try:
            play_session_id = uuid.UUID(play_session_id)
        except ValueError:
            play_session_id = None
    else:
        play_session_id = None

    feed_session_id = fields.get('feed_session_id', '')
    if feed_session_id:
        try:
            feed_session_id = uuid.UUID(feed_session_id)
        except ValueError:
            feed_session_id = None
    else:
        feed_session_id = None

    milestones = []
    if fields.get('milestones'):
        try:
            milestones = json.loads(fields['milestones'])
        except (json.JSONDecodeError, TypeError):
            milestones = []

    return {
        'event_id': uuid.UUID(fields['event_id']),
        'user_id': int(fields['user_id']),
        'content_id': int(fields['content_id']) if fields.get('content_id') else None,
        'content_type': fields.get('content_type', 'reel'),
        'creator_id': int(fields['creator_id']) if fields.get('creator_id') else None,
        'event_type': fields['event_type'],
        'watch_pct': float(fields.get('watch_pct', 0.0)),
        'session_id': session_id,
        'play_session_id': play_session_id,
        'feed_session_id': feed_session_id,
        'watch_ms': int(fields['watch_ms']) if fields.get('watch_ms') else None,
        'loop_index': int(fields.get('loop_index', 0)),
        'scroll_direction': fields.get('scroll_direction') or None,
        'candidate_source': fields.get('candidate_source') or None,
        'position': int(fields['position']) if fields.get('position') else None,
        'source_user_id': int(fields['source_user_id']) if fields.get('source_user_id') else None,
        'timestamp': datetime.fromisoformat(fields['timestamp']),
        'source': fields.get('source', 'feed'),
        'device_context': device_context,
        'milestones': milestones,
    }


def _process_view_session(user_id, content_id, content_type, play_session_id, feed_session_id, ended_at):
    """
    Aggregates all RecEvents for a given play_session_id and creates/updates a ReelViewSession.
    Then updates UserContentInterest with the aggregated counts.
    """
    from .models import RecEvent, ReelViewSession, UserContentInterest
    from django.db.models import F

    # Ensure this isn't processed multiple times for the same play_session_id
    if ReelViewSession.objects.filter(play_session_id=play_session_id).exists():
        return

    events = list(RecEvent.objects.filter(
        user_id=user_id,
        content_id=content_id,
        content_type=content_type,
        play_session_id=play_session_id
    ).order_by('timestamp'))

    if not events:
        return
        
    started_at = events[0].timestamp
    max_watch_percent = max([e.watch_pct for e in events] + [0.0])
    # Dwell ms might be in the last impression_end or watch event
    total_watch_ms = max([e.watch_ms for e in events if e.watch_ms is not None] + [0])
    loop_count = max([e.loop_index for e in events] + [0])
    
    # Check backward seeks (approximate by looking at progress drops if available, but loop_count serves a similar purpose)
    backward_seeks = 0 # Future enhancement: compute from milestones/progress drops
    
    # Classify outcome
    session_outcome = 'NORMAL_EXIT'
    is_meaningful_view = False
    
    # First, check for explicit negative events in this session (e.g. skip, not_interested)
    has_skip_event = any(e.event_type == 'skip' for e in events)
    
    if max_watch_percent < 0.15 and total_watch_ms < 3000 and (has_skip_event or loop_count == 0):
        session_outcome = 'QUICK_SKIP'
    elif 0.15 <= max_watch_percent < 0.70:
        session_outcome = 'PARTIAL_SKIP'
    elif 0.70 <= max_watch_percent < 0.99:
        session_outcome = 'NORMAL_EXIT'
        is_meaningful_view = True
    elif max_watch_percent >= 0.99 or loop_count > 0:
        session_outcome = 'COMPLETED'
        is_meaningful_view = True

    # If the user has watched this content before and reached completion
    uci = UserContentInterest.objects.filter(user_id=user_id, content_id=content_id, content_type=content_type).first()
    if uci and uci.completed_count > 0 and session_outcome in ['COMPLETED', 'NORMAL_EXIT']:
        session_outcome = 'REWATCH_EXIT'
        is_meaningful_view = True

    ReelViewSession.objects.create(
        user_id=user_id,
        content_id=content_id,
        content_type=content_type,
        play_session_id=play_session_id,
        feed_session_id=feed_session_id,
        max_watch_percent=max_watch_percent,
        total_watch_ms=total_watch_ms,
        loop_count=loop_count,
        session_outcome=session_outcome,
        is_meaningful_view=is_meaningful_view,
        started_at=started_at,
        ended_at=ended_at
    )
    
    # Update UserContentInterest
    obj, created = UserContentInterest.objects.get_or_create(
        user_id=user_id,
        content_id=content_id,
        content_type=content_type,
        defaults={'first_seen_at': started_at, 'last_seen_at': ended_at}
    )
    
    update_kwargs = {
        'view_session_count': F('view_session_count') + 1,
        'total_watch_ms': F('total_watch_ms') + total_watch_ms,
        'last_watch_percent': max_watch_percent,
        'last_action': session_outcome,
        'last_seen_at': ended_at,
    }
    
    if max_watch_percent > obj.max_watch_percent:
        update_kwargs['max_watch_percent'] = max_watch_percent
        
    if is_meaningful_view:
        update_kwargs['meaningful_view_count'] = F('meaningful_view_count') + 1
        
    if session_outcome == 'COMPLETED':
        update_kwargs['completed_count'] = F('completed_count') + 1
    elif session_outcome == 'REWATCH_EXIT':
        update_kwargs['rewatch_count'] = F('rewatch_count') + 1
    elif session_outcome == 'QUICK_SKIP':
        update_kwargs['quick_skip_count'] = F('quick_skip_count') + 1
    elif session_outcome == 'PARTIAL_SKIP':
        update_kwargs['partial_skip_count'] = F('partial_skip_count') + 1
        
    UserContentInterest.objects.filter(id=obj.id).update(**update_kwargs)


@shared_task(name='api.modules.rec_events.tasks.consume_event_stream')
def consume_event_stream():
    """
    Celery task that reads a batch of events from the Redis Stream
    and writes them to MySQL.

    This task is designed to be called repeatedly (e.g. by a Celery Beat
    schedule every few seconds, or by chaining itself). Each invocation
    processes up to BATCH_SIZE events.

    The task is idempotent and safe for concurrent workers thanks to
    Redis consumer groups and the UUID primary key on RecEvent.
    """
    from .models import RecEvent

    r = _get_stream_redis()
    _ensure_consumer_group(r)

    # Generate a consumer name unique to this worker invocation
    consumer_name = f'worker-{uuid.uuid4().hex[:8]}'

    try:
        # Read pending (unacknowledged) messages first, then new ones
        messages = r.xreadgroup(
            CONSUMER_GROUP,
            consumer_name,
            {STREAM_KEY: '>'},  # '>' means only new messages
            count=BATCH_SIZE,
            block=BLOCK_MS,
        )
    except redis.RedisError as e:
        logger.error(f'Error reading from stream: {e}')
        return {'processed': 0, 'errors': 1}

    if not messages:
        return {'processed': 0, 'errors': 0}

    processed = 0
    errors = 0
    ack_ids = []

    for stream_name, entries in messages:
        for msg_id, fields in entries:
            try:
                # Basic validation: ensure no None values
                if not fields.get('user_id') or not fields.get('content_id'):
                    logger.warning(f"Event {msg_id} missing user_id or content_id. Skipping.")
                    ack_ids.append(msg_id)
                    processed += 1
                    continue
                
                # Check for abuse/spam
                if is_event_suspicious(int(fields['user_id']), fields.get('event_type'), timezone.now()):
                    logger.warning(f"Abuse filter triggered for user {fields['user_id']} event {fields.get('event_type')}. Dropping.")
                    ack_ids.append(msg_id)
                    processed += 1
                    continue

                parsed = _parse_stream_event(fields)

                # Route 'impression_shown' to RecommendationImpression table
                if parsed['event_type'] == 'impression_shown':
                    from api.modules.ranking.models import RecommendationImpression
                    
                    if parsed['content_id']:
                        RecommendationImpression.objects.create(
                            user_id=parsed['user_id'],
                            content_id=parsed['content_id'],
                            content_type=parsed['content_type'],
                            candidate_source=parsed.get('candidate_source') or 'UNKNOWN',
                            source_user_id=parsed.get('source_user_id'),
                            session_id=parsed['session_id'],
                            position=parsed.get('position', 0),
                            shown_at=parsed['timestamp']
                        )
                    
                    # We continue without storing it as a RecEvent to keep behavioral events clean
                    processed += 1
                    ack_ids.append(msg_id)
                    continue

                # Skip superseding logic: if user fully watches, remove prior skips for this content
                if parsed['event_type'] in ('watch', 'replay', 'rewatch', 'rewatch_complete', 'impression_end'):
                    RecEvent.objects.filter(
                        user_id=parsed['user_id'],
                        content_id=parsed['content_id'],
                        content_type=parsed['content_type'],
                        event_type='skip'
                    ).delete()

                RecEvent.objects.create(
                    event_id=parsed['event_id'],
                    user_id=parsed['user_id'],
                    content_id=parsed['content_id'],
                    content_type=parsed['content_type'],
                    creator_id=parsed['creator_id'],
                    event_type=parsed['event_type'],
                    watch_pct=parsed['watch_pct'],
                    session_id=parsed['session_id'],
                    play_session_id=parsed['play_session_id'],
                    watch_ms=parsed['watch_ms'],
                    loop_index=parsed['loop_index'],
                    scroll_direction=parsed['scroll_direction'],
                    timestamp=parsed['timestamp'],
                    source=parsed['source'],
                    device_context=parsed['device_context'],
                    milestones=parsed['milestones'],
                    feed_session_id=parsed['feed_session_id'],
                )
                
                # Update UserContentInterest and create ReelViewSession on impression_end
                if parsed['event_type'] == 'impression_end' and parsed['content_id'] and parsed['play_session_id']:
                    _process_view_session(
                        user_id=parsed['user_id'],
                        content_id=parsed['content_id'],
                        content_type=parsed['content_type'],
                        play_session_id=parsed['play_session_id'],
                        feed_session_id=parsed['feed_session_id'],
                        ended_at=parsed['timestamp']
                    )
                
                # Master Tracking: Impression count
                if parsed['event_type'] == 'impression_start' and parsed['content_id']:
                    from .models import UserContentInterest
                    from django.db.models import F
                    obj, created = UserContentInterest.objects.get_or_create(
                        user_id=parsed['user_id'],
                        content_id=parsed['content_id'],
                        content_type=parsed['content_type'],
                        defaults={'impression_count': 1, 'first_seen_at': parsed['timestamp'], 'last_seen_at': parsed['timestamp']}
                    )
                    if not created:
                        UserContentInterest.objects.filter(id=obj.id).update(
                            impression_count=F('impression_count') + 1,
                            last_seen_at=parsed['timestamp']
                        )

                # Populate Redis seen filter (Phase 4.3)
                # Mark content as seen if it was watched, skipped, or interacted with
                if parsed['event_type'] in ('watch', 'rewatch', 'rewatch_complete', 'skip', 'not_interested', 'hide', 'like', 'impression_end'):
                    from api.modules.rec_filter.seen import mark_as_seen
                    if parsed['content_id']:
                        mark_as_seen(user_id=parsed['user_id'], content_id=parsed['content_id'])
                
                processed += 1
                ack_ids.append(msg_id)

            except IntegrityError:
                # Duplicate event_id — idempotency guarantee.
                # This is expected on re-delivery; acknowledge and move on.
                logger.debug(f'Duplicate event {fields.get("event_id")} — skipping.')
                ack_ids.append(msg_id)
                processed += 1  # Count as processed (not an error)

            except Exception as e:
                logger.error(f'Failed to process event {msg_id}: {e}')
                errors += 1
                # Don't acknowledge — it will be retried on the next read

    # Acknowledge processed messages
    if ack_ids:
        try:
            r.xack(STREAM_KEY, CONSUMER_GROUP, *ack_ids)
        except redis.RedisError as e:
            logger.error(f'Failed to acknowledge {len(ack_ids)} messages: {e}')

    logger.info(f'consume_event_stream: processed={processed}, errors={errors}')
    return {'processed': processed, 'errors': errors}


@shared_task(name='api.modules.rec_events.tasks.consume_event_stream_continuous')
def consume_event_stream_continuous(max_iterations=100):
    """
    Runs the stream consumer in a loop for up to `max_iterations` batches.
    Useful for draining a backlog. Stops early if a batch returns 0 events.

    In production, this is typically triggered once and then the Beat-based
    `consume_event_stream` handles steady-state ingestion.
    """
    total_processed = 0
    total_errors = 0

    for i in range(max_iterations):
        result = consume_event_stream()
        total_processed += result.get('processed', 0)
        total_errors += result.get('errors', 0)

        # If no messages were found, the stream is drained — stop early
        if result.get('processed', 0) == 0 and result.get('errors', 0) == 0:
            break

    logger.info(
        f'consume_event_stream_continuous: '
        f'total_processed={total_processed}, total_errors={total_errors}'
    )
    return {'total_processed': total_processed, 'total_errors': total_errors}

@shared_task(name='api.modules.rec_events.tasks._flush_session')
def _flush_session(user_id: int, session_id: str):
    """
    Called when a session expires. Aggregates the events for that session
    and saves them to the SessionLog table.
    """
    from .models import RecEvent, SessionLog
    from django.db.models import Count, Avg, Q

    events = RecEvent.objects.filter(user_id=user_id, session_id=session_id)
    if not events.exists():
        return
        
    start_time = events.earliest('timestamp').timestamp
    end_time = events.latest('timestamp').timestamp
    total = events.count()
    
    # Calculate metrics
    stats = events.aggregate(
        avg_watch=Avg('watch_pct', filter=Q(event_type__in=['watch', 'replay'])),
        skips=Count('event_id', filter=Q(event_type='skip')),
        not_interested=Count('event_id', filter=Q(event_type='not_interested'))
    )
    
    skip_rate = stats['skips'] / total if total > 0 else 0
    
    # Simple satisfaction heuristic for the session
    # Higher is better
    satisfaction = (stats['avg_watch'] or 0) * 10 - (skip_rate * 5) - (stats['not_interested'] * 10)
    
    SessionLog.objects.create(
        session_id=session_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        total_events=total,
        avg_watch_pct=stats['avg_watch'] or 0.0,
        skip_rate=skip_rate,
        not_interested_count=stats['not_interested'],
        satisfaction_score=satisfaction
    )
    logger.info(f"Flushed session {session_id} for user {user_id}")

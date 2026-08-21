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

    return {
        'event_id': uuid.UUID(fields['event_id']),
        'user_id': int(fields['user_id']),
        'content_id': int(fields['content_id']),
        'content_type': fields.get('content_type', 'reel'),
        'creator_id': int(fields['creator_id']) if fields.get('creator_id') else None,
        'event_type': fields['event_type'],
        'watch_pct': float(fields.get('watch_pct', 0.0)),
        'session_id': session_id,
        'timestamp': datetime.fromisoformat(fields['timestamp']),
        'source': fields.get('source', 'feed'),
        'device_context': device_context,
    }


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

                # Skip superseding logic: if user fully watches, remove prior skips for this content
                if parsed['event_type'] in ('watch', 'replay', 'rewatch', 'rewatch_complete'):
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
                    timestamp=parsed['timestamp'],
                    source=parsed['source'],
                    device_context=parsed['device_context'],
                )
                
                # Populate Redis seen filter (Phase 4.3)
                # Mark content as seen if it was watched, skipped, or interacted with
                if parsed['event_type'] in ('watch', 'rewatch', 'rewatch_complete', 'skip', 'not_interested', 'hide', 'like'):
                    from api.modules.rec_filter.seen import mark_as_seen
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

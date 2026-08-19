import redis
import os
from dotenv import load_dotenv

load_dotenv('.env')

# The stream key from tasks.py
STREAM_KEY = 'user-events'

r = redis.Redis.from_url(os.environ.get('REDIS_STREAMS_URL', 'redis://localhost:6379/2'), decode_responses=True)

try:
    # Read up to 10 messages from the beginning of the stream
    messages = r.xread({STREAM_KEY: '0'}, count=10)
    if not messages:
        print("No events currently in the Redis stream 'user-events'.")
    else:
        print("--- EVENTS IN REDIS STREAM ---")
        for stream_name, entries in messages:
            for msg_id, fields in entries:
                print(f"ID: {msg_id} -> {fields}")
except redis.exceptions.ConnectionError:
    print("Could not connect to Redis.")
except Exception as e:
    print(f"Error: {e}")

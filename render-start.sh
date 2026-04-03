#!/usr/bin/env bash
set -o errexit

# Run Daphne ASGI server to support WebSockets / Django Channels instead of WSGI
daphne vibely_backend.asgi:application --port $PORT --bind 0.0.0.0

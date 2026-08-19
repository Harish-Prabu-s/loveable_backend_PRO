"""
Celery Application Configuration
=================================
Central Celery app for the Vibely backend.

- Broker: Redis (same instance as channels, different DB number)
- Result backend: Redis
- Auto-discovers tasks from all installed Django apps
- Beat schedule defined here for periodic recommendation engine jobs

Start worker:   celery -A vibely_backend worker -l info
Start beat:     celery -A vibely_backend beat -l info
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vibely_backend.settings')

app = Celery('vibely_backend')

# Read config from Django settings, namespace='CELERY' means all
# celery-related settings must be prefixed with CELERY_ in settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

from django.conf import settings

# Auto-discover tasks.py in all installed apps AND our custom submodules
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS + [
    'api.modules.rec_events',
    'api.modules.ranking',
    'api.modules.feature_store',
    'api.modules.embeddings',
    'api.modules.rec_privacy'
])


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Diagnostic task — prints the request info. Use to verify Celery is running."""
    print(f'Request: {self.request!r}')

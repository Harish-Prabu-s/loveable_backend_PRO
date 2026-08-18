import pymysql

pymysql.install_as_MySQLdb()

# Load Celery app so that @shared_task decorators use this app.
from .celery import app as celery_app

__all__ = ('celery_app',)

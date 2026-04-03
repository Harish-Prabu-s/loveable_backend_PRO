"""
Management command: send_scheduled_notifs
Usage: python manage.py send_scheduled_notifs --hour=9
       (Valid hours: 9, 13, 18, 22 — matches the 4 scheduled push times)

Schedule via cron:
  0 9  * * * cd /app && python manage.py send_scheduled_notifs --hour=9
  0 13 * * * cd /app && python manage.py send_scheduled_notifs --hour=13
  0 18 * * * cd /app && python manage.py send_scheduled_notifs --hour=18
  0 22 * * * cd /app && python manage.py send_scheduled_notifs --hour=22
"""
from django.core.management.base import BaseCommand
from api.modules.notifications.push_service import send_scheduled_push


class Command(BaseCommand):
    help = 'Send scheduled multilingual emotional push notifications'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hour',
            type=int,
            choices=[9, 13, 18, 22],
            required=True,
            help='Hour slot to send (9, 13, 18, or 22)',
        )

    def handle(self, *args, **options):
        hour = options['hour']
        self.stdout.write(f'Sending scheduled push notifications for hour={hour}...')
        result = send_scheduled_push(hour)
        self.stdout.write(
            self.style.SUCCESS(
                f'Done! Sent: {result["sent"]}, Errors: {result["errors"]}'
            )
        )

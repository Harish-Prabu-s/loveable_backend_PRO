import os
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from api.models import Profile, Wallet

class Command(BaseCommand):
    help = "Create a default superuser with profile and wallet if not exists"

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'admin123')

        user, created = User.objects.get_or_create(username=username, defaults={'email': email})
        if created:
            user.is_staff = True
            user.is_superuser = True
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f"Created superuser '{username}'"))
        else:
            self.stdout.write(self.style.WARNING(f"Superuser '{username}' already exists"))

        # Ensure profile
        Profile.objects.get_or_create(user=user, defaults={'phone_number': '0000000000', 'is_verified': True})

        # Ensure wallet
        Wallet.objects.get_or_create(user=user)

        self.stdout.write(self.style.SUCCESS("Profile and wallet ensured for superuser"))

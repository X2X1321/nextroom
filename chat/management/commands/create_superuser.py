from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

import os

class Command(BaseCommand):
    help = 'Create a staff/admin user from environment variables if it does not already exist.'

    def handle(self, *args, **options):
        admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

        if not admin_username or not admin_password:
            self.stdout.write(self.style.WARNING('DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set in environment. Skipping superuser creation.'))
            return

        if User.objects.filter(username=admin_username).exists():
            user = User.objects.get(username=admin_username)
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                user.set_password(admin_password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Updated existing admin user with staff/superuser flags.'))
            else:
                user.set_password(admin_password)
                user.save()
                self.stdout.write(self.style.WARNING(f'Admin already exists. Password reset.'))
            return
        user = User.objects.create_superuser(
            username=admin_username,
            email=f'{admin_username}@example.com',
            password=admin_password,
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser created: {user.username}'))

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

import os

class Command(BaseCommand):
    help = 'Create an admin user if one does not already exist.'

    def handle(self, *args, **options):
        admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
        admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not admin_username or not admin_password:
            self.stdout.write(self.style.WARNING('DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set. Skipping.'))
            return
            
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('Superuser already exists. No changes made.'))
            return
        user = User.objects.create_superuser(
            username=admin_username,
            email=f'{admin_username}@example.com',
            password=admin_password,
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser created: {user.username}'))

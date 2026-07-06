from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create an admin user if one does not already exist.'

    def handle(self, *args, **options):
        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write(self.style.WARNING('Superuser already exists. No changes made.'))
            return
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123',
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser created: {user.username} / admin123'))

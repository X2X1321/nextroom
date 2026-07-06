from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a staff/admin user with username=admin and password=183564 if it does not already exist.'

    def handle(self, *args, **options):
        if User.objects.filter(username='admin').exists():
            user = User.objects.get(username='admin')
            if not user.is_staff or not user.is_superuser:
                user.is_staff = True
                user.is_superuser = True
                user.set_password('183564')
                user.save()
                self.stdout.write(self.style.SUCCESS('Updated existing admin user with staff/superuser flags and password 183564.'))
            else:
                user.set_password('183564')
                user.save()
                self.stdout.write(self.style.WARNING('Admin already exists. Password reset to 183564.'))
            return
        user = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='183564',
        )
        self.stdout.write(self.style.SUCCESS(f'Superuser created: {user.username} / 183564'))

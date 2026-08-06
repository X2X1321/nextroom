from django.core.management import call_command
from django.contrib.auth import get_user_model

User = get_user_model()


import os

def ensure_superuser():
    admin_username = os.environ.get('DJANGO_SUPERUSER_USERNAME')
    admin_password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    if not admin_username or not admin_password:
        return
    if User.objects.filter(username=admin_username).exists():
        return
    try:
        User.objects.create_superuser(admin_username, f'{admin_username}@example.com', admin_password)
    except Exception:
        try:
            call_command('create_superuser', verbosity=0)
        except Exception:
            pass


def bootstrap():
    try:
        call_command('migrate', '--run-syncdb', verbosity=0)
    except Exception:
        pass
    ensure_superuser()

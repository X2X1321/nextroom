from django.core.management import call_command
from django.contrib.auth import get_user_model

User = get_user_model()


def ensure_superuser():
    if User.objects.filter(username='admin').exists():
        return
    try:
        User.objects.create_superuser('admin', 'admin@example.com', '183564')
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

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nextroom_project.settings')
django.setup()

from nextroom_project.bootstrap import cleanup_corrupted_integrations
cleanup_corrupted_integrations()
print("Success")

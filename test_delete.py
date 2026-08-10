import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nextroom_project.settings')
django.setup()

from chat.models import AIIntegration
print("Deleting all integrations...")
AIIntegration.objects.all().delete()
print("Done!")

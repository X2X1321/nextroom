import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nextroom_project.settings')
os.environ['DJANGO_SECRET_KEY'] = 'dummy'
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from chat.views import routerai_keys_view

user = User.objects.first()
factory = RequestFactory()
request = factory.get('/ai-management/my-keys/')
request.user = user

try:
    response = routerai_keys_view(request)
    print("STATUS:", response.status_code)
except Exception as e:
    import traceback
    traceback.print_exc()

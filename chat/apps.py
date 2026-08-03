from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'

    def ready(self):
        try:
            from .models import _ensure_achievements
            _ensure_achievements()
        except Exception:
            pass

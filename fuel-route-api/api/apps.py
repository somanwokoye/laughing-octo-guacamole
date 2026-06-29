from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import sys
        if 'runserver' in sys.argv or 'gunicorn' in sys.argv[0:1]:
            from api.services import warm_station_cache
            warm_station_cache()

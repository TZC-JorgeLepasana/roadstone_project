from django.apps import AppConfig

class DataProcessingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'data_processing'
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)))  # Explicit absolute path
    
    def ready(self):
        # Import models to prevent double registration
        from .models import ProcessedFile, ParsingSchedule  # noqa
        # Skip signals import if file doesn't exist
        try:
            from . import signals  # noqa
        except ImportError:
            pass

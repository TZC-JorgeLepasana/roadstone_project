import os
from celery import Celery
from celery.schedules import crontab
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'roadstone_project.settings')

app = Celery('roadstone_project')

# Timezone setup (Dublin)
app.conf.enable_utc = True
app.conf.timezone = 'Europe/Dublin'  # Must match settings.TIME_ZONE

# Load task modules from all registered Django apps
app.config_from_object('django.conf:settings', namespace='CELERY')

# Periodic Tasks (REQUIRED for crontab to work)
app.conf.beat_schedule = {
    'parse-every-hour': {
        'task': 'data_processing.tasks.process_xml_files',
        'schedule': crontab(minute=0, hour='*/1'),  # Runs hourly at :00
        'kwargs': {'schedule_id': 1}  # Optional: Pass schedule ID
    },
}

app.autodiscover_tasks(['data_processing'])
app.conf.broker_connection_retry_on_startup = True
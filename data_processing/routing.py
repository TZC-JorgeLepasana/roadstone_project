# data_processing/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/parsing_progress/$', consumers.ParsingProgressConsumer.as_asgi()),
    re_path(r'ws/energy/(?P<task_id>\w+)/$', consumers.EnergyDataConsumer.as_asgi()),
]
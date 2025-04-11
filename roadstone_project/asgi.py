"""
ASGI config for roadstone_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""


import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from data_processing.routing import websocket_urlpatterns
from . import routing 

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'roadstone_project.settings')

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": URLRouter(
        URLRouter(
            routing.websocket_urlpatterns
        )
    ),
})

import json
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from celery.result import AsyncResult

class ParsingProgressConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs'].get('task_id')
        self.group_name = f'parsing_{self.task_id}' if self.task_id else 'parsing_updates'

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def progress_update(self, event):
        await self.send(text_data=json.dumps(event['data']))

    async def send_progress_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'progress.update',
            'files_processed': event['files_processed'],
            'batches_processed': event['batches_processed'],
            'current_file': event['current_file'],
            'progress': event['progress']
        }))

class EnergyDataConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.task_id = self.scope['url_route']['kwargs']['task_id']
        await self.channel_layer.group_add(
            f"energy_{self.task_id}",
            self.channel_name
        )
        await self.accept()

    async def receive(self, text_data):
        # Handle incoming messages if needed
        pass

    async def task_update(self, event):
        await self.send_json(event['data'])
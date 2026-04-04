import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from .matchmaking_redis import MatchmakingQueueService
from django.contrib.auth.models import User
from api.models import Profile, MatchmakingLog
from channels.db import database_sync_to_async

class MatchmakingConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.monitor_task = None

    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return

        self.group_name = f"matchmaking_{self.user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if self.monitor_task:
            self.monitor_task.cancel()
        
        await database_sync_to_async(MatchmakingQueueService.remove_user)(self.user.id)
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'join_matchmaking':
            await self.handle_join_matchmaking(data)
        
        elif action == 'expand_search':
            await self.handle_expand_search(data)
            
        elif action == 'invite_to_game':
            await self.handle_invite_to_game(data)
        
        elif action == 'cancel_matchmaking':
            await self.handle_cancel_matchmaking()

    async def handle_join_matchmaking(self, data):
        mode = data.get('mode', '2p')
        game_type = data.get('game_type', 'truth_dare') # e.g. romantic, flirty, etc.
        gender = await self.get_user_gender()
        
        await self.send(text_data=json.dumps({
            'event': 'SEARCHING',
            'mode': mode,
            'game_type': game_type,
            'gender': gender
        }))

        match = await database_sync_to_async(MatchmakingQueueService.add_user)(
            self.user.id, mode, gender, game_type
        )

        if match:
            await self.dispatch_match_events(match)
        else:
            if self.monitor_task: self.monitor_task.cancel()
            self.monitor_task = asyncio.create_task(self.monitor_matchmaking())

    async def handle_expand_search(self, data):
        """
        Switches the user to the 'ANY' gender queue for faster matching.
        """
        mode = data.get('mode', '2p')
        game_type = data.get('game_type', 'truth_or_dare')
        gender = await self.get_user_gender()
        
        await self.send(text_data=json.dumps({
            'event': 'EXPANDING_SEARCH',
            'mode': mode
        }))

        match = await database_sync_to_async(MatchmakingQueueService.add_user)(
            self.user.id, mode, gender, game_type, expanded=True
        )

        if match:
            await self.dispatch_match_events(match)

    async def handle_invite_to_game(self, data):
        """
        Sends a private game invite to a specific user.
        """
        target_user_id = data.get('target_user_id')
        game_type = data.get('game_type', 'truth_or_dare')
        
        if not target_user_id: return

        # Broadcast to target user's group
        await self.channel_layer.group_send(
            f"matchmaking_{target_user_id}",
            {
                'type': 'game_invite_received',
                'sender_id': self.user.id,
                'sender_name': self.user.username,
                'game_type': game_type,
                'room_code': data.get('room_code')
            }
        )
        
        await self.send(text_data=json.dumps({
            'event': 'INVITE_SENT'
        }))

    async def game_invite_received(self, event):
        """
        Handles incoming private game invite from another user.
        """
        await self.send(text_data=json.dumps({
            'event': 'GAME_INVITE',
            'sender_id': event['sender_id'],
            'sender_name': event['sender_name'],
            'game_type': event['game_type'],
            'room_code': event['room_code']
        }))

    async def handle_cancel_matchmaking(self):
        if self.monitor_task: self.monitor_task.cancel()
        success = await database_sync_to_async(MatchmakingQueueService.remove_user)(self.user.id)
        if success:
            await self.send(text_data=json.dumps({'event': 'MATCH_CANCELLED'}))

    async def monitor_matchmaking(self):
        try:
            await asyncio.sleep(45)
            await self.send(text_data=json.dumps({
                'event': 'MATCH_TIMEOUT',
                'message': 'Partner finding is taking longer than usual. Stay in queue or expand search?',
                'options': ['STAY', 'EXPAND']
            }))
            await self.log_matchmaking_status('timeout')
        except asyncio.CancelledError:
            pass

    async def dispatch_match_events(self, match):
        for uid in match['players']:
            await self.channel_layer.group_send(
                f"matchmaking_{uid}",
                {
                    'type': 'match_found',
                    'room_code': match['room_code'],
                    'session_id': match['session_id']
                }
            )

    async def match_found(self, event):
        if self.monitor_task: self.monitor_task.cancel()
        await self.send(text_data=json.dumps({
            'event': 'MATCH_FOUND',
            'room_code': event['room_code'],
            'session_id': event['session_id']
        }))

    @database_sync_to_async
    def get_user_gender(self):
        try: return self.user.profile.gender or 'O'
        except: return 'O'

    @database_sync_to_async
    def log_matchmaking_status(self, status):
        MatchmakingLog.objects.create(user=self.user, mode='searching', status=status)

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)



class BaseRealtimeConsumer(AsyncWebsocketConsumer):
    """
    Base consumer providing common functionality like heartbeat (ping/pong)
    and user-specific group management.
    """
    channel_type = "base"


    async def connect(self):
        self.user_id = self.scope['url_route']['kwargs'].get('user_id')
        if not self.user_id:
            await self.close()
            return

        self.group_name = f"{self.channel_type}_{self.user_id}"
        
        # Log connection attempt
        logger.info(f"[WS] Connecting {self.channel_type} for user {self.user_id} | Group: {self.group_name}")
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        await self.accept()
        logger.info(f"[WS] Accepted {self.channel_type} for user {self.user_id}")

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            logger.info(f"[WS] Disconnecting {self.channel_type} for user {self.user_id} | Code: {close_code}")
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Standard heartbeat
            if data.get('type') == 'ping':
                logger.info(f"[WS] Ping from user {self.user_id}")
                await self.send(text_data=json.dumps({'type': 'pong'}))
            else:
                await self.handle_custom_event(data)
        except json.JSONDecodeError:
            logger.warning(f"[WS] Invalid JSON received from user {self.user_id}")

    async def handle_custom_event(self, data):
        """Override in subclasses to handle client-sent events"""
        pass

class NotificationConsumer(BaseRealtimeConsumer):
    channel_type = "notifications"

    async def send_notification(self, event):
        """Handler for 'send_notification' group messages"""
        await self.send(text_data=json.dumps(event['content']))

    async def group_call_alert(self, event):
        """Specific handler for incoming group calls"""
        await self.send(text_data=json.dumps({
            'type': 'incoming_group_call',
            'room_id': event['room_id'],
            'caller_name': event['caller_name'],
            'call_type': event['call_type']
        }))

class ChatConsumer(BaseRealtimeConsumer):
    channel_type = "chat"

    @database_sync_to_async
    def get_room_participants(self, room_id):
        from api.models import Room, RoomMember
        try:
            room = Room.objects.get(id=room_id)
            if room.is_group:
                return list(RoomMember.objects.filter(room=room).values_list('user_id', flat=True))
            return [room.caller_id, room.receiver_id]
        except Room.DoesNotExist:
            return []

    async def handle_custom_event(self, data):
        # Handle typing indicators etc.
        if data.get('type') == 'typing':
            room_id = data.get('room_id')
            is_typing = data.get('is_typing', False)
            if not room_id:
                return

            # Lookup room participants
            participants = await self.get_room_participants(room_id)
            for u_id in participants:
                if str(u_id) != str(self.user_id):
                    await self.channel_layer.group_send(
                        f'chat_{u_id}',
                        {
                            'type': 'send_message',
                            'content': {
                                'type': 'typing_status',
                                'room_id': room_id,
                                'from_user_id': self.user_id,
                                'is_typing': is_typing
                            }
                        }
                    )
        
        elif data.get('type') == 'update_theme':
            room_id = data.get('room_id')
            theme = data.get('theme', 'default')
            if not room_id: return

            # Sync to DB
            await self.update_room_theme(room_id, theme)

            # Relay to all participants
            participants = await self.get_room_participants(room_id)
            for u_id in participants:
                if str(u_id) != str(self.user_id):
                    await self.channel_layer.group_send(
                        f'chat_{u_id}',
                        {
                            'type': 'send_message',
                            'content': {
                                'type': 'theme_updated',
                                'room_id': room_id,
                                'theme': theme
                            }
                        }
                    )

        elif data.get('type') == 'message_reaction':
            room_id = data.get('room_id')
            message_id = data.get('message_id')
            emoji = data.get('emoji')
            if not room_id or not message_id: return

            # Relay to all participants
            participants = await self.get_room_participants(room_id)
            for u_id in participants:
                if str(u_id) != str(self.user_id):
                    await self.channel_layer.group_send(
                        f'chat_{u_id}',
                        {
                            'type': 'send_message',
                            'content': {
                                'type': 'reaction_updated',
                                'message_id': message_id,
                                'room_id': room_id,
                                'user_id': self.user_id,
                                'emoji': emoji
                            }
                        }
                    )
        
        elif data.get('type') == 'mark_seen':
            room_id = data.get('room_id')
            if not room_id: return

            # Relay to all participants
            participants = await self.get_room_participants(room_id)
            for u_id in participants:
                if str(u_id) != str(self.user_id):
                    await self.channel_layer.group_send(
                        f'chat_{u_id}',
                        {
                            'type': 'send_message',
                            'content': {
                                'type': 'messages_seen',
                                'room_id': room_id,
                                'user_id': self.user_id
                            }
                        }
                    )

    @database_sync_to_async
    def update_room_theme(self, room_id, theme):
        from api.models import Room
        Room.objects.filter(id=room_id).update(chat_theme=theme)

    async def send_message(self, event):
        """Handler for 'send_message' group messages"""
        await self.send(text_data=json.dumps(event['content']))

class CallConsumer(BaseRealtimeConsumer):
    channel_type = "call"

    async def incoming_call(self, event):
        """Handler for 'incoming_call' group messages (Incoming alert)"""
        await self.send(text_data=json.dumps(event['content']))

class CallRoomConsumer(AsyncWebsocketConsumer):
    """
    Production-grade WebRTC signaling consumer.
    Handles targeted signalling between peers and tracks room state.
    """
    @database_sync_to_async
    def get_user_profile_data(self):
        """
        Safely fetch profile data in a synchronous database context.
        This prevents 'RelatedObjectDoesNotExist' and async event loop crashes.
        """
        try:
            profile = getattr(self.user, 'profile', None)
            if profile:
                photo_url = None
                if profile.photo:
                    try:
                        photo_url = profile.photo.url if hasattr(profile.photo, 'url') else str(profile.photo)
                    except Exception:
                        photo_url = None
                return {
                    'display_name': profile.display_name or self.user.username,
                    'photo': photo_url
                }
        except Exception as e:
            logger.error(f"[WS Call] Error fetching profile for user {getattr(self.user, 'id', 'unknown')}: {e}")
        
        return {
            'display_name': getattr(self.user, 'username', 'Unknown User'),
            'photo': None
        }

    async def connect(self):
        try:
            self.room_id = str(self.scope['url_route']['kwargs']['room_id'])
            self.room_group_name = f'call_room_{self.room_id}'
            self.user = self.scope.get('user')
    
            if not self.user or self.user.is_anonymous:
                logger.warning(f"[WS Call] REJECTED: User is Anonymous or Token invalid. Room: {self.room_id}")
                await self.close(code=4001)
                return
    
            self.user_id = self.user.id
            logger.info(f"[WS Call] Authenticated user {self.user_id} connecting to room {self.room_id}")
            
            # Add to room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            await self.accept()
            logger.info(f"[WS Call] User {self.user_id} ACCEPTED. Room: {self.room_id}")
    
            # 1. Track presence (Join)
            await self.track_presence(join=True)
            
            # 2. Notify others and get current participants
            profile_data = await self.get_user_profile_data()
    
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_joined',
                    'user_id': self.user_id,
                    'display_name': profile_data['display_name'],
                    'photo': profile_data['photo'],
                    'from_channel': self.channel_name
                }
            )

            # 4. SEND EXISTING PARTICIPANTS TO THE NEW USER
            # This ensures both sides recognize each other even if they join at slightly different times.
            active_participants = await self.get_active_participants()
            for pid, metadata in active_participants.items():
                if str(pid) != str(self.user_id):
                    await self.send(text_data=json.dumps({
                        'type': 'participant-joined',
                        'user_id': pid,
                        'from_user_id': pid,
                        'display_name': metadata.get('display_name'),
                        'photo': metadata.get('photo')
                    }))
            
            logger.info(f"[WS Call] User {self.user_id} joined room {self.room_id}")
        except Exception as e:
            logger.error(f"[WS Call] Connection failed with error: {str(e)}")
            await self.close(code=1011)

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # 1. Remove from presence
            await self.track_presence(join=False)
            
            # 2. Notify others
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_left',
                    'user_id': self.user_id
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            logger.info(f"[WS Call] User {self.user_id} left room {self.room_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get('type')
            target_id = data.get('target_user_id')

            # Attach sender info
            data['from_user_id'] = self.user_id

            if msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong', 'timestamp': data.get('timestamp')}))
                return

            if msg_type in ['call-offer', 'call-answer', 'ice-candidate', 'call-accept', 'call-reject']:
                if target_id:
                    logger.info(f"[WS Signaling] Relaying TARGETED {msg_type} from {self.user_id} to {target_id} | Room: {self.room_id}")
                    # Targeted signal to a specific user
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'relay_signal',
                            'message': data,
                            'target_user_id': target_id
                        }
                    )
                else:
                    logger.info(f"[WS Signaling] BROADCASTING {msg_type} from {self.user_id} | Room: {self.room_id}")
                    # Broadcast signal (only for specific room-wide events)
                    await self.channel_layer.group_send(
                        self.room_group_name,
                        {
                            'type': 'relay_signal',
                            'message': data
                        }
                    )
            
            elif msg_type == 'chat-message':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': data
                    }
                )

            elif msg_type == 'media-state' or msg_type == 'screen-share':
                # Broadcast media state changes (mute, video off)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'relay_signal',
                        'message': data
                    }
                )

        except Exception as e:
            logger.error(f"[WS Call] Error handling message: {e}")

    # ── Group Message Handlers ───────────────────────────────────────────────

    async def participant_joined(self, event):
        # Notify client about a new participant
        if str(event['user_id']) != str(self.user_id):
            await self.send(text_data=json.dumps({
                'type': 'participant-joined',
                'user_id': event['user_id'],
                'from_user_id': event['user_id'],  # Robustness: align with from_user_id
                'display_name': event['display_name'],
                'photo': event['photo']
            }))

    async def participant_left(self, event):
        if str(event['user_id']) != str(self.user_id):
            await self.send(text_data=json.dumps({
                'type': 'participant-left',
                'user_id': event['user_id'],
                'from_user_id': event['user_id']
            }))

    # ── Presence Helpers ─────────────────────────────────────────────────────

    async def track_presence(self, join=True):
        """Track user presence in the room using the channel layer or cache."""
        from django.core.cache import cache
        presence_key = f"presence_{self.room_group_name}"
        
        # Get profile data safely
        profile_data = await self.get_user_profile_data()
        user_info = {
            'user_id': self.user_id,
            'display_name': profile_data['display_name'],
            'photo': profile_data['photo']
        }
        
        current_presence = cache.get(presence_key, {})
        if join:
            current_presence[str(self.user_id)] = user_info
        else:
            current_presence.pop(str(self.user_id), None)
            
        cache.set(presence_key, current_presence, timeout=3600) # 1 hour TTL
    async def get_active_participants(self):
        """Fetch current presence from cache."""
        from django.core.cache import cache
        presence_key = f"presence_{self.room_group_name}"
        return cache.get(presence_key, {})

    async def relay_signal(self, event):
        message = event['message']
        target_id = event.get('target_user_id')

        # If targeted, only send to the target
        if target_id is not None:
            if str(target_id) == str(self.user_id):
                await self.send(text_data=json.dumps(message))
        else:
            # Broadcast to everyone EXCEPT sender
            if str(message.get('from_user_id')) != str(self.user_id):
                await self.send(text_data=json.dumps(message))

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

class CatchAllConsumer(AsyncWebsocketConsumer):
    """
    Diagnostic consumer that catches all unmatched WebSocket paths
    and logs the attempt. This helps identify routing discrepancies.
    """
    async def connect(self):
        path = self.scope.get('path', 'unknown')
        logger.warning(f"[WS ROUTER] UNMATCHED PATH: {path}")
        await self.close(code=4004) # Not Found

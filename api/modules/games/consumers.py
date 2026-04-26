import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from api.models import GameRoom, InteractiveGameSession, PlayerState, QuestionBank, GameEventLog
from django.contrib.auth.models import User
import random
from .couple_game_consumer import CoupleGameConsumer

class GameConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'game_session_{self.session_id}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        
        # Connect logic
        await self.handle_player_join()

    async def disconnect(self, close_code):
        await self.handle_player_leave()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('action')

        if event_type == 'start_game':
            await self.handle_start_game()
        elif event_type == 'submit_action':
            await self.handle_submit_action(data.get('payload'))
        elif event_type == 'cast_vote':
            await self.handle_cast_vote(data.get('vote'))

    async def handle_player_join(self):
        session, created = await self.get_or_create_session()
        await self.set_player_status(session, True)
        players = await self.get_connected_players(session)
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_message',
                'event': 'PlayerJoined',
                'players': players
            }
        )

    async def handle_player_leave(self):
        session = await self.get_current_session()
        if session:
            await self.set_player_status(session, False)

    async def handle_start_game(self):
        session = await self.get_current_session()
        if session and session.current_state == 'Waiting':
            session = await self.update_session_state(session, 'TurnAssigned')
            await self.log_event(session, 'GameStarted', {})
            
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_message',
                    'event': 'GameStarted',
                    'state': 'TurnAssigned'
                }
            )
            # Boot up the turn engine
            await self.assign_next_turn(session)

    async def assign_next_turn(self, session):
        player, task = await self.turn_engine_pick(session)
        if player and task:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_message',
                    'event': 'TurnAssigned',
                    'player_id': player.id,
                    'task': task.text,
                    'task_type': task.question_type
                }
            )

    async def handle_submit_action(self, payload):
        session = await self.get_current_session()
        # For board games, we might not have a "current_turn_player" set in DB yet, 
        # but we check if session exists.
        if session:
            await self.update_session_action(session, payload)
            
            # Broadcast the action to everyone
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'game_message',
                    'event': 'ActionBroadcast',
                    'player_id': self.user.id,
                    'payload': payload
                }
            )

    async def handle_cast_vote(self, vote):
        session = await self.get_current_session()
        if session and session.current_state == 'VotingState':
            result = await self.register_vote(session, vote)
            if result == 'done':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'game_message',
                        'event': 'RoundEnded',
                        'passed': session.votes_pass > session.votes_fail
                    }
                )
                # Next turn
                await self.assign_next_turn(session)

    async def game_message(self, event):
        await self.send(text_data=json.dumps(event))

    # --- DB UTILS ---
    @database_sync_to_async
    def get_or_create_session(self):
        session = InteractiveGameSession.objects.get(id=self.session_id)
        return session, False

    @database_sync_to_async
    def get_current_session(self):
        return InteractiveGameSession.objects.filter(id=self.session_id).first()

    @database_sync_to_async
    def set_player_status(self, session, status):
        ps, _ = PlayerState.objects.get_or_create(session=session, user=self.user)
        ps.is_connected = status
        ps.save()

    @database_sync_to_async
    def get_connected_players(self, session):
        qs = PlayerState.objects.filter(session=session, is_connected=True)
        return [{'id': p.user.id, 'username': p.user.username} for p in qs]

    @database_sync_to_async
    def update_session_state(self, session, state):
        session.current_state = state
        session.save()
        return session

    @database_sync_to_async
    def turn_engine_pick(self, session):
        ps = list(PlayerState.objects.filter(session=session, is_connected=True))
        if not ps: return None, None
        
        # Simple random turn engine avoiding immediate repeat if >1 player
        candidates = [p.user for p in ps]
        if len(candidates) > 1 and session.current_turn_player in candidates:
            candidates.remove(session.current_turn_player)
            
        next_player = random.choice(candidates)
        
        # Pick random Truth/Dare based on room type
        room = session.room
        if room and room.room_type == 'couple':
            qs = QuestionBank.objects.all() # Couples can get any
        elif room and room.room_type == 'random':
            qs = QuestionBank.objects.filter(safety_level='safe')
        else:
            qs = QuestionBank.objects.filter(safety_level__in=['safe', 'mature'])
            
        tasks = list(qs)
        if not tasks:
            tasks = [QuestionBank.objects.create(question_type='truth', text='What is your biggest fear?', safety_level='safe')]
            
        task = random.choice(tasks)
        
        session.current_turn_player = next_player
        session.active_prompt = task
        session.current_state = 'ActionPending'
        session.votes_pass = 0
        session.votes_fail = 0
        session.save()
        
        return next_player, task

    @database_sync_to_async
    def update_session_action(self, session, payload):
        session.action_payload = payload
        session.current_state = 'VotingState'
        session.save()

    @database_sync_to_async
    def register_vote(self, session, vote):
        if vote == 'pass':
            session.votes_pass += 1
        else:
            session.votes_fail += 1
        session.save()
        
        total_players = PlayerState.objects.filter(session=session, is_connected=True).count()
        # If everyone except the active player voted
        if (session.votes_pass + session.votes_fail) >= (total_players - 1):
            session.current_state = 'ResultState'
            session.save()
            return 'done'
        return 'waiting'

    @database_sync_to_async
    def log_event(self, session, event_type, payload):
        GameEventLog.objects.create(
            session=session,
            actor=self.user,
            event_type=event_type,
            payload=payload
        )

# ----------------------------------------------------------------------------
# MATCHMAKING ENGINE
# ----------------------------------------------------------------------------
from api.models import MatchmakingQueue, GameRoom
from asgiref.sync import sync_to_async

class MatchmakingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if self.user.is_anonymous:
            await self.close()
            return
            
        # Join personal group for direct messages like MatchFound
        self.user_group_name = f"user_{self.user.id}"
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user_group_name'):
            await self.channel_layer.group_discard(
                self.user_group_name,
                self.channel_name
            )
        await self.remove_from_queue()

    async def receive(self, text_data):
        data = json.loads(text_data)
        event_type = data.get('action')

        if event_type == 'search_match':
            mode = data.get('mode', '2p')
            gender = await self.get_user_gender()
            if not gender:
                await self.send(text_data=json.dumps({'event': 'Error', 'message': 'Gender must be set in Profile'}))
                return
                
            await self.add_to_queue(mode, gender)
            await self.send(text_data=json.dumps({'event': 'Searching', 'mode': mode}))
            # Trigger match engine check
            await self.check_match()
            
        elif event_type == 'cancel_search':
            await self.remove_from_queue()
            await self.send(text_data=json.dumps({'event': 'SearchCancelled'}))

    @database_sync_to_async
    def get_user_gender(self):
        if hasattr(self.user, 'profile') and self.user.profile.gender:
            return self.user.profile.gender
        return 'M' # Default fallback if missing for demo purposes

    @database_sync_to_async
    def add_to_queue(self, mode, gender):
        MatchmakingQueue.objects.update_or_create(
            user=self.user,
            defaults={'mode': mode, 'gender': gender}
        )

    @database_sync_to_async
    def remove_from_queue(self):
        MatchmakingQueue.objects.filter(user=self.user).delete()

    async def check_match(self):
        match_data = await self._find_and_create_match()
        if match_data:
            # We found a match. Send to self.
            await self.send(text_data=json.dumps(match_data))
            
            # To notify the other user, we use group_send to their personal channel
            channel_layer = self.channel_layer
            await channel_layer.group_send(
                f"user_{match_data['opponent_id']}",
                {
                    'type': 'match_message',
                    'event': 'MatchFound',
                    'room_id': match_data['room_id']
                }
            )

    @database_sync_to_async
    def _find_and_create_match(self):
        my_entry = MatchmakingQueue.objects.filter(user=self.user).first()
        if not my_entry: return None
        
        mode = my_entry.mode
        my_gender = my_entry.gender
        
        if mode == '2p':
            target_gender = 'F' if my_gender == 'M' else 'M'
            target_entry = MatchmakingQueue.objects.filter(
                mode='2p', gender=target_gender
            ).exclude(user=self.user).order_by('joined_at').first()
            
            if target_entry:
                import uuid
                room_code = str(uuid.uuid4())[:8]
                new_room = GameRoom.objects.create(
                    room_code=room_code,
                    room_type='random',
                    status='waiting'
                )
                
                MatchmakingQueue.objects.filter(user__in=[self.user, target_entry.user]).delete()
                return {
                    'event': 'MatchFound', 
                    'room_id': new_room.id, 
                    'opponent_id': target_entry.user.id
                }
        return None

    # Handle messages sent via group_send to user's personal channel
    async def match_message(self, event):
        await self.send(text_data=json.dumps(event))

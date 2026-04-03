import json
import random
from datetime import timedelta
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from api.models import Room, GameRoom, InteractiveGameSession, PlayerState, QuestionBank, GameEventLog
from django.contrib.auth.models import User

class TruthOrDareConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'tod_{self.room_id}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
        await self.handle_player_join()

    async def disconnect(self, close_code):
        await self.handle_player_leave()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')

        if action == 'start_game':
            await self.handle_start_game()
        elif action == 'select_option':
            await self.handle_select_option(data.get('option')) # 'truth' or 'dare'
        elif action == 'submit_task':
            await self.handle_submit_task(data.get('task_text'))
        elif action == 'complete_task':
            await self.handle_complete_task()
        elif action == 'quit_game':
            await self.handle_quit_game()

    async def handle_player_join(self):
        session, created = await self.get_or_create_session()
        await self.set_player_status(session, True)
        players = await self.get_connected_players(session)
        
        await self.broadcast({
            'event': 'PlayerJoined',
            'players': players,
            'state': session.current_state
        })

    async def handle_player_leave(self):
        session = await self.get_current_session()
        if session:
            await self.set_player_status(session, False)

    async def handle_start_game(self):
        session = await self.get_current_session()
        # Only start if Waiting or EndState
        if session and session.current_state in ['Waiting', 'EndState']:
            await self.broadcast({
                'event': 'GameStarted'
            })
            await self.start_next_turn(session)

    async def start_next_turn(self, session):
        player, questioner = await self.assign_turn_roles(session)
        if player:
            await self.broadcast({
                'event': 'TurnAssigned',
                'active_player_id': player.id,
                'active_player_name': player.username,
                'questioner_id': questioner.id if questioner else None,
                'questioner_name': questioner.username if questioner else 'System'
            })
        else:
            await self.broadcast({
                'event': 'GameEnded',
                'reason': 'Not enough players'
            })

    async def handle_select_option(self, option):
        session = await self.get_current_session()
        if not session or session.current_state != 'TURN_ACTIVE': return
        if session.current_turn_player != self.user: return
        if option not in ['truth', 'dare']: return

        await self.update_selected_option(session, option)
        
        await self.broadcast({
            'event': 'OptionSelected',
            'player_id': self.user.id,
            'option': option
        })

        # If questioner is a user, we wait for SUBMIT_TASK. 
        # If questioner is System (None), we auto-assign task.
        if not session.current_questioner_player:
            task = await self.get_system_task(session, option)
            await self.assign_and_broadcast_task(session, task.text if task else "Do a generic dare!")

    async def handle_submit_task(self, task_text):
        session = await self.get_current_session()
        if not session or session.current_state != 'TASK_ASSIGNED': return
        if session.current_questioner_player != self.user: return

        await self.assign_and_broadcast_task(session, task_text)

    async def assign_and_broadcast_task(self, session, task_text):
        await self.set_session_task(session, task_text)
        await self.broadcast({
            'event': 'TaskCreated',
            'task': task_text,
            'option': session.selected_option
        })
        await self.broadcast({
            'event': 'TimerStarted',
            'duration': 120
        })

    async def handle_complete_task(self):
        session = await self.get_current_session()
        if not session or session.current_state != 'AWAITING_RESPONSE': return
        
        # Only questioner can click Complete. If system is questioner, active player clicks it? 
        # Let's say if system is questioner, active player can click complete.
        if session.current_questioner_player:
            if session.current_questioner_player != self.user: return
        else:
            if session.current_turn_player != self.user: return

        # Check timer
        is_success = await self.process_task_completion(session)
        
        await self.broadcast({
            'event': 'TaskResult',
            'success': is_success,
            'player_id': session.current_turn_player.id,
            'points': 10 if is_success else -5
        })

        # Send updated scores
        scores = await self.get_player_scores(session)
        await self.broadcast({
            'event': 'ScoreUpdate',
            'scores': scores
        })

        # Wait a moment or immediately next turn
        await self.start_next_turn(session)

    async def handle_quit_game(self):
        session = await self.get_current_session()
        if not session: return
        
        # Apply penalty
        await self.apply_quit_penalty(session, self.user)
        
        await self.broadcast({
            'event': 'PlayerQuit',
            'player_id': self.user.id,
            'penalty': -10
        })

        scores = await self.get_player_scores(session)
        await self.broadcast({
            'event': 'ScoreUpdate',
            'scores': scores
        })

        # If they were active, skip turn
        if session.current_turn_player == self.user:
            await self.start_next_turn(session)

    async def broadcast(self, event_data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'tod_message',
                **event_data
            }
        )

    async def tod_message(self, event):
        # Send message to WebSocket
        # event is dict, just dump it
        await self.send(text_data=json.dumps(event))

    # --- DB UTILS ---
    @database_sync_to_async
    def get_or_create_session(self):
        try:
            room = GameRoom.objects.get(room_code=self.room_id)
        except GameRoom.DoesNotExist:
            room = None
        
        if not room:
            # Fallback to Room if needed, or create dynamically for demo
            room, _ = GameRoom.objects.get_or_create(room_code=self.room_id, defaults={'room_type': 'group'})

        session, created = InteractiveGameSession.objects.get_or_create(
            room=room,
            defaults={'current_state': 'Waiting'}
        )
        return session, created

    @database_sync_to_async
    def get_current_session(self):
        return InteractiveGameSession.objects.filter(room__room_code=self.room_id).last()

    @database_sync_to_async
    def set_player_status(self, session, status):
        ps, _ = PlayerState.objects.get_or_create(session=session, user=self.user)
        ps.is_connected = status
        ps.save()

    @database_sync_to_async
    def get_connected_players(self, session):
        qs = PlayerState.objects.filter(session=session, is_connected=True)
        return [{'id': p.user.id, 'username': p.user.username, 'score': p.score} for p in qs]

    @database_sync_to_async
    def get_player_scores(self, session):
        qs = PlayerState.objects.filter(session=session)
        return {p.user.id: p.score for p in qs}

    @database_sync_to_async
    def assign_turn_roles(self, session):
        ps = list(PlayerState.objects.filter(session=session, is_connected=True))
        if len(ps) < 2:
            session.current_state = 'EndState'
            session.save()
            return None, None
            
        candidates = [p.user for p in ps]
        if session.current_turn_player in candidates:
            candidates.remove(session.current_turn_player)
            
        next_player = random.choice(candidates) if candidates else ps[0].user
        
        # Assign questioner
        other_players = [p.user for p in ps if p.user != next_player]
        questioner = random.choice(other_players) if other_players else None

        session.current_turn_player = next_player
        session.current_questioner_player = questioner
        session.current_state = 'TURN_ACTIVE'
        session.selected_option = None
        session.timer_started_at = None
        session.action_payload = None 
        session.save()
        
        return next_player, questioner

    @database_sync_to_async
    def update_selected_option(self, session, option):
        session.selected_option = option
        session.current_state = 'TASK_ASSIGNED'
        session.save()

    @database_sync_to_async
    def get_system_task(self, session, option):
        room = session.room
        if room and room.room_type == 'couple':
            qs = QuestionBank.objects.filter(question_type=option)
        else:
            qs = QuestionBank.objects.filter(question_type=option, safety_level='safe')
            
        tasks = list(qs)
        return random.choice(tasks) if tasks else None

    @database_sync_to_async
    def set_session_task(self, session, task_text):
        session.action_payload = {'task_text': task_text}
        session.current_state = 'AWAITING_RESPONSE'
        session.timer_started_at = timezone.now()
        session.save()

    @database_sync_to_async
    def process_task_completion(self, session):
        # Check if within 2 minutes + small grace
        now = timezone.now()
        is_success = False
        if session.timer_started_at and (now - session.timer_started_at) <= timedelta(seconds=130):
            is_success = True
            
        ps, _ = PlayerState.objects.get_or_create(session=session, user=session.current_turn_player)
        if is_success:
            ps.score += 10
        else:
            ps.score -= 5
        ps.save()
        
        session.current_state = 'COMPLETED' if is_success else 'FAILED'
        session.save()
        return is_success

    @database_sync_to_async
    def apply_quit_penalty(self, session, user):
        ps, _ = PlayerState.objects.get_or_create(session=session, user=user)
        ps.score -= 10
        ps.save()

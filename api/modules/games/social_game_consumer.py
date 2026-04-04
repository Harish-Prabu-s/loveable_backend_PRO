import json
import random
import asyncio
from datetime import timedelta
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from api.models import GameRoom, InteractiveGameSession, PlayerState, QuestionBank, GameEventLog, UserRelationship, LevelProgress
from django.contrib.auth.models import User
from django.db.models import Q

class SocialGameConsumer(AsyncWebsocketConsumer):
    """
    Unified Multi-Mode Social Interaction Engine.
    Supports 9+ modes: Truth/Dare, Romantic, Deep, Flirty, Roleplay, Memory, Draw&Guess, Co-op, Random Match.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timer_task = None
        self.coop_validators = set() # For checking multiple completions

    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'game_{self.room_id}'
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
        if self.timer_task:
            self.timer_task.cancel()
        await self.handle_player_leave()
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        payload = data.get('payload', {})

        if action == 'start_game':
            await self.handle_start_game()
        elif action == 'select_option':
            await self.handle_select_option(payload.get('option'))
        elif action == 'submit_input':
            await self.handle_submit_input(payload)
        elif action == 'complete_task':
            await self.handle_complete_task(success=True)
        elif action == 'fail_task':
            await self.handle_complete_task(success=False)
        elif action == 'draw_update':
            await self.handle_draw_update(payload)
        elif action == 'quit_game':
            await self.handle_quit_game()

    async def handle_player_join(self):
        session, created = await self.get_or_create_session()
        await self.set_player_status(session, True)
        players = await self.get_connected_players(session)
        
        await self.broadcast({
            'event': 'PlayerJoined',
            'players': players,
            'state': session.current_state,
            'mode': session.room.game_mode,
            'active_player_id': session.current_turn_player.id if session.current_turn_player else None
        })

    async def handle_player_leave(self):
        session = await self.get_current_session()
        if session:
            await self.set_player_status(session, False)

    async def handle_start_game(self):
        session = await self.get_current_session()
        if session and session.current_state in ['Waiting', 'EndState', 'lobby']:
            await self.broadcast({'event': 'GameStarted'})
            await self.start_next_turn(session)

    async def start_next_turn(self, session):
        if self.timer_task: self.timer_task.cancel()
        self.coop_validators.clear()

        # 🎡 Spinning Wheel Event
        await self.broadcast({'event': 'SpinningWheel'})
        await asyncio.sleep(2)

        player, questioner = await self.assign_turn_roles(session)
        if not player:
            await self.broadcast({'event': 'GameEnded', 'reason': 'Not enough players'})
            return

        # Prepare mode-specific turn config
        mode = session.room.game_mode
        mode_config = self.get_mode_turn_config(mode)

        await self.broadcast({
            'event': 'TurnAssigned',
            'active_player_id': player.id,
            'active_player_name': player.username,
            'questioner_id': questioner.id if questioner else None,
            'questioner_name': questioner.username if questioner else 'System',
            'mode_config': mode_config
        })

    def get_mode_turn_config(self, mode):
        """Logic Switch for Mode UI/Behaviour"""
        configs = {
            'romantic': {'options': ['truth'], 'input_required': True},
            'deep': {'options': ['truth'], 'input_required': True},
            'flirty': {'options': ['dare'], 'input_required': False},
            'roleplay': {'options': ['dare'], 'input_required': True},
            'draw_guess': {'options': ['draw'], 'input_required': False},
            'coop': {'options': ['task'], 'input_required': False},
            'truth_dare': {'options': ['truth', 'dare'], 'input_required': False},
            'random_match': {'options': ['truth', 'dare'], 'input_required': False, 'safe_mode': True},
        }
        return configs.get(mode, configs['truth_dare'])

    async def handle_select_option(self, option):
        session = await self.get_current_session()
        if not session or session.current_state != 'TURN_ACTIVE': return
        if session.current_turn_player != self.user: return

        # Validate based on mode
        mode = session.room.game_mode
        config = self.get_mode_turn_config(mode)
        if option not in config['options']: return

        await self.update_selected_option(session, option)
        await self.broadcast({
            'event': 'OptionSelected',
            'player_id': self.user.id,
            'option': option
        })

        # If system is questioner or mode is auto, assign task
        if not session.current_questioner_player and not config['input_required']:
            task = await self.get_system_task(session, option)
            await self.assign_and_broadcast_task(session, task.text if task else "Challenge accepted!")

    async def handle_submit_input(self, payload):
        """Questioner types a question or scenario"""
        session = await self.get_current_session()
        if not session or session.current_state not in ['TURN_ACTIVE', 'TASK_ASSIGNED']: return
        
        # Only questioner can submit input
        if session.current_questioner_player != self.user: return

        task_text = payload.get('text')
        await self.assign_and_broadcast_task(session, task_text)

    async def handle_draw_update(self, payload):
        """Real-time drawing broadcast"""
        # We don't save every stroke to DB, just broadcast
        await self.broadcast({
            'event': 'DrawingUpdate',
            'data': payload.get('drawing_data'),
            'player_id': self.user.id
        })

    async def assign_and_broadcast_task(self, session, task_text):
        await self.set_session_task(session, task_text)
        await self.broadcast({
            'event': 'TaskCreated',
            'task': task_text,
            'option': session.selected_option,
            'mode': session.room.game_mode
        })
        
        await self.broadcast({'event': 'TimerStarted', 'duration': 120})
        
        if self.timer_task: self.timer_task.cancel()
        self.timer_task = asyncio.create_task(self.start_timer_logic(session.id))

    async def start_timer_logic(self, session_id):
        try:
            await asyncio.sleep(125)
            await self.handle_auto_fail(session_id)
        except asyncio.CancelledError: pass

    async def handle_auto_fail(self, session_id):
        session = await self.get_session_by_id(session_id)
        if session and session.current_state == 'AWAITING_RESPONSE':
            await self.handle_complete_task(success=False, is_auto=True)

    async def handle_complete_task(self, success=True, is_auto=False):
        session = await self.get_current_session()
        if not session or session.current_state != 'AWAITING_RESPONSE': return
        
        mode = session.room.game_mode
        
        # 🤝 Co-op Logic: wait for both
        if mode == 'coop' and success and not is_auto:
            self.coop_validators.add(self.user.id)
            players_count = await self.get_connected_count(session)
            if len(self.coop_validators) < players_count:
                await self.broadcast({'event': 'CoopProgress', 'count': len(self.coop_validators)})
                return

        # Regular Validation
        if not is_auto and mode != 'coop':
            if session.current_questioner_player:
                if session.current_questioner_player != self.user: return
            else:
                if session.current_turn_player != self.user: return

        if self.timer_task: self.timer_task.cancel()
        
        result = await self.process_task_result(session, success)
        
        await self.broadcast({
            'event': 'TaskResult',
            'success': success,
            'auto_fail': is_auto,
            'player_id': session.current_turn_player.id,
            'points_granted': result['points_granted']
        })

        scores = await self.get_player_scores(session)
        await self.broadcast({'event': 'ScoreUpdate', 'scores': scores})

        await asyncio.sleep(3)
        await self.start_next_turn(session)

    async def handle_quit_game(self):
        session = await self.get_current_session()
        if not session: return
        await self.apply_quit_penalty(session, self.user)
        await self.broadcast({'event': 'PlayerQuit', 'player_id': self.user.id, 'penalty': -10})
        scores = await self.get_player_scores(session)
        await self.broadcast({'event': 'ScoreUpdate', 'scores': scores})
        if session.current_turn_player == self.user:
            await self.start_next_turn(session)

    async def broadcast(self, event_data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {'type': 'game_message', **event_data}
        )

    async def game_message(self, event):
        await self.send(text_data=json.dumps(event))

    # --- DATABASE OPERATIONS (Optimized) ---
    @database_sync_to_async
    def get_or_create_session(self):
        try:
            room = GameRoom.objects.get(room_code=self.room_id)
        except GameRoom.DoesNotExist:
            room = GameRoom.objects.create(room_code=self.room_id, room_type='random', game_mode='truth_dare')
        
        session, created = InteractiveGameSession.objects.get_or_create(room=room, defaults={'current_state': 'Waiting'})
        return session, created

    @database_sync_to_async
    def get_current_session(self):
        return InteractiveGameSession.objects.filter(room__room_code=self.room_id).select_related('room').last()

    @database_sync_to_async
    def get_session_by_id(self, sid):
        return InteractiveGameSession.objects.filter(id=sid).first()

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
    def get_connected_count(self, session):
        return PlayerState.objects.filter(session=session, is_connected=True).count()

    @database_sync_to_async
    def get_player_scores(self, session):
        qs = PlayerState.objects.filter(session=session)
        return {p.user.id: p.score for p in qs}

    @database_sync_to_async
    def assign_turn_roles(self, session):
        ps_list = list(PlayerState.objects.filter(session=session, is_connected=True))
        if len(ps_list) < 2: return None, None
            
        history = list(session.turn_history or [])
        all_ids = [p.user.id for p in ps_list]
        candidates = [pid for pid in all_ids if pid not in history]
        if not candidates:
            candidates = all_ids
            history = []
            
        chosen_id = random.choice(candidates)
        history.append(chosen_id)
        next_player = User.objects.get(id=chosen_id)
        
        other_players = [p.user for p in ps_list if p.user.id != chosen_id]
        questioner = random.choice(other_players) if other_players else None

        session.current_turn_player = next_player
        session.current_questioner_player = questioner
        session.current_state = 'TURN_ACTIVE'
        session.turn_history = history
        session.selected_option = None
        session.save()
        return next_player, questioner

    @database_sync_to_async
    def update_selected_option(self, session, option):
        session.selected_option = option
        session.current_state = 'TASK_ASSIGNED'
        session.save()

    @database_sync_to_async
    def get_system_task(self, session, option):
        cat = 'general'
        if session.room.game_mode == 'flirty': cat = 'flirty'
        tasks = list(QuestionBank.objects.filter(question_type=option, category=cat))
        return random.choice(tasks) if tasks else None

    @database_sync_to_async
    def set_session_task(self, session, task_text):
        session.action_payload = {'task_text': task_text}
        session.current_state = 'AWAITING_RESPONSE'
        session.timer_started_at = timezone.now()
        session.save()

    @database_sync_to_async
    def process_task_result(self, session, success):
        performer_ps = PlayerState.objects.get(session=session, user=session.current_turn_player)
        points_granted = 0
        
        if success:
            performer_ps.score += 10
            points_granted = 10
            # XP
            lp, _ = LevelProgress.objects.get_or_create(user=session.current_turn_player)
            lp.xp += 20
            lp.save()
            # Relationship meter for Memory/Connection modes
            if session.room.game_mode in ['romantic', 'memory', 'deep']:
                other = session.players.exclude(user=session.current_turn_player).first()
                if other:
                    u1, u2 = sorted([session.current_turn_player.id, other.user.id])
                    rel, _ = UserRelationship.objects.get_or_create(user_one_id=u1, user_two_id=u2)
                    rel.closeness_score += 5
                    rel.save()
            
            if session.current_questioner_player:
                q_ps = PlayerState.objects.get(session=session, user=session.current_questioner_player)
                q_ps.score += 5
                q_ps.save()
        else:
            performer_ps.score -= 5
            points_granted = -5
            
        performer_ps.save()
        session.current_state = 'RESULT_WAIT'
        session.save()
        return {'points_granted': points_granted}

    @database_sync_to_async
    def apply_quit_penalty(self, session, user):
        ps, _ = PlayerState.objects.get_or_create(session=session, user=user)
        ps.score -= 10
        ps.save()

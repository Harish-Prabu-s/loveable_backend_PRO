import json
import random
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from api.models import (
    Room, InteractiveGameSession, PlayerState, QuestionBank, 
    GameEventLog, GameRoom, UserRelationship
)
from django.contrib.auth.models import User

class CoupleGameConsumer(AsyncWebsocketConsumer):
    """
    State machine for couple-specific interactive games.
    Supports 6 modes with custom logic for consent, turn-taking, and scoring.
    """
    
    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'couple_game_session_{self.session_id}'
        self.user = self.scope['user']

        if self.user.is_anonymous:
            # Code 4001 indicates Auth Failure
            await self.close(code=4001)
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()
        
        # Initialize player state
        session = await self.get_or_create_session()
        await self.set_player_status(session, True)
        
        await self.broadcast_game_update('PlayerJoined', {
            'player_id': self.user.id,
            'username': self.user.username,
            'display_name': getattr(self.user.profile, 'display_name', self.user.username)
        })

    async def disconnect(self, close_code):
        session = await self.get_current_session()
        if session:
            await self.set_player_status(session, False)
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        action = data.get('action')
        payload = data.get('payload', {})

        if action == 'start_game':
            await self.handle_start_game(payload.get('mode', 'truth_dare'))
        elif action == 'give_consent':
            await self.handle_consent()
        elif action == 'submit_answer':
            await self.handle_submit_answer(payload)
        elif action == 'submit_custom_prompt':
            await self.handle_submit_custom_prompt(payload)
        elif action == 'verify_response':
            await self.handle_verification(payload)
        elif action == 'reaction':
            await self.broadcast_game_update('ReactionReceived', {
                'from_user': self.user.id,
                'reaction': payload.get('type')
            })
        elif action == 'draw_data':
            # Real-time drawing sync
            await self.broadcast_game_update('DrawDataReceived', {
                'from_user': self.user.id,
                'path': payload.get('path')
            })

    async def handle_start_game(self, mode):
        session = await self.get_current_session()
        if not session: return

        # Check for Spicy mode consent requirement
        if mode == 'spicy':
            await self.update_session_state(session, 'WaitingConsent')
            await self.broadcast_game_update('GameStateChanged', {
                'state': 'WaitingConsent',
                'mode': mode,
                'message': 'Both partners must click "I Consent" to proceed with spicy content.'
            })
        else:
            await self.start_round(session, mode)

    async def handle_consent(self):
        session = await self.get_current_session()
        # Add user to consent list in payload
        consented = await self.register_consent(session, self.user.id)
        
        if len(consented) >= 2:
            await self.start_round(session, 'spicy')
        else:
            await self.broadcast_game_update('ConsentLogged', {
                'user_id': self.user.id,
                'count': len(consented)
            })

    async def start_round(self, session, mode):
        # Pick player and prompt
        player, prompt = await self.turn_engine_pick(session, mode)
        
        await self.broadcast_game_update('RoundStarted', {
            'mode': mode,
            'current_player': player.id,
            'state': 'PromptPending'
        })

    async def handle_submit_custom_prompt(self, payload):
        session = await self.get_current_session()
        custom_text = payload.get('text', '')
        
        # 1. Update session with custom prompt in payload
        # No QuestionBank id needed anymore
        await self.save_custom_prompt(session, custom_text)
        
        await self.broadcast_game_update('PromptSubmitted', {
            'player_id': self.user.id,
            'prompt_text': custom_text,
            'state': 'ActionPending'
        })

    async def handle_submit_answer(self, payload):
        session = await self.get_current_session()
        # Payload might contain text or image_url
        await self.save_submission(session, payload)
        
        await self.broadcast_game_update('AnswerSubmitted', {
            'player_id': self.user.id,
            'answer': payload.get('text', ''),
            'media': payload.get('media_url', None),
            'state': 'VerificationPending'
        })

    async def handle_verification(self, payload):
        session = await self.get_current_session()
        is_approved = payload.get('approved', True)
        score_diff = 10 if is_approved else 0
        
        # Update session score
        new_score = await self.update_player_score(session, score_diff)
        
        await self.broadcast_game_update('ResponseVerified', {
            'approved': is_approved,
            'total_score': new_score,
            'comment': payload.get('comment', '')
        })
        
        # Auto-trigger next round after delay or manual next
        await self.start_round(session, session.room.game_mode)

    async def broadcast_game_update(self, event, data):
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'game_event',
                'event': event,
                'data': data
            }
        )

    async def game_event(self, event):
        await self.send(text_data=json.dumps(event))

    # --- DATABASE OPERATIONS ---
    
    @database_sync_to_async
    def get_or_create_session(self):
        # Use session directly
        session = InteractiveGameSession.objects.get(id=self.session_id)
        return session

    @database_sync_to_async
    def get_current_session(self):
        return InteractiveGameSession.objects.filter(id=self.session_id).first()

    @database_sync_to_async
    def set_player_status(self, session, status):
        ps, _ = PlayerState.objects.get_or_create(session=session, user=self.user)
        ps.is_connected = status
        ps.save()

    @database_sync_to_async
    def register_consent(self, session, user_id):
        payload = session.action_payload or {}
        consent_list = payload.get('consented', [])
        if user_id not in consent_list:
            consent_list.append(user_id)
        payload['consented'] = consent_list
        session.action_payload = payload
        session.save()
        return consent_list

    @database_sync_to_async
    def update_session_state(self, session, state):
        session.current_state = state
        session.save()

    @database_sync_to_async
    def turn_engine_pick(self, session, mode):
        # 1. Update GameRoom mode if changed
        room = session.room
        room.game_mode = mode
        room.save()

        # 2. Pick next player (toggle in 1v1)
        players = list(PlayerState.objects.filter(session=session, is_connected=True))
        if len(players) < 2:
            return self.user, QuestionBank.objects.first() # Edge case
            
        next_player = players[0].user if session.current_turn_player_id != players[0].user_id else players[1].user
        
        # 3. Filter QuestionBank
        is_stranger = room.room_type == 'random'
        qs = QuestionBank.objects.filter(category=mode)
        
        if is_stranger:
            qs = qs.filter(safety_level='safe')
        
        if not qs.exists():
            # Fallback to general/icebreakers if category empty
            qs = QuestionBank.objects.filter(category='stranger' if is_stranger else 'romantic')
            if not qs.exists():
                qs = QuestionBank.objects.all()
            
        prompt = random.choice(list(qs))
        
        session.current_turn_player = next_player
        session.active_prompt = None # No default question used
        session.current_state = 'PromptPending'
        session.save()
        
        return next_player, None

    @database_sync_to_async
    def save_custom_prompt(self, session, text):
        payload = session.action_payload or {}
        payload['custom_prompt'] = text
        session.action_payload = payload
        session.current_state = 'ActionPending'
        session.save()
        return session

    @database_sync_to_async
    def save_submission(self, session, payload):
        session.action_payload = payload
        session.current_state = 'VerificationPending'
        session.save()

    @database_sync_to_async
    def update_player_score(self, session, diff):
        # Update session score
        ps = PlayerState.objects.filter(session=session, user=self.user).first()
        if ps:
            ps.score += diff
            ps.save()
        
        # Update relationship closeness score
        if diff > 0:
            players = list(PlayerState.objects.filter(session=session))
            if len(players) >= 2:
                u1, u2 = sorted([players[0].user_id, players[1].user_id])
                rel, _ = UserRelationship.objects.get_or_create(user_one_id=u1, user_two_id=u2)
                rel.closeness_score += (diff // 2) # Slower growth for relationship
                rel.save()

        # Total room score
        total = sum(p.score for p in PlayerState.objects.filter(session=session))
        return total

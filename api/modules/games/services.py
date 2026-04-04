from ...models import Game, Notification
import random
from django.contrib.auth.models import User
from ..notifications.services import create_notification

def list_active_games():
    return Game.objects.filter(is_active=True).order_by('name')

def send_game_invite(sender: User, recipient_id: int, game_id: str):
    """
    Sends a game invitation to a specific user.
    Creates a notification and sends real-time data via WebSockets.
    """
    try:
        recipient = User.objects.get(id=recipient_id)
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        # 1. Create DB Notification
        msg = f"{sender.username} invited you to play {game_id.replace('_', ' ').title()}!"
        create_notification(
            recipient=recipient,
            actor=sender,
            notification_type='game_invite',
            message=msg,
            object_id=None # Optionally link to a session if pre-created
        )
        
        # 2. Real-time WebSocket Invite
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{recipient.id}',
                {
                    'type': 'send_notification',
                    'content': {
                        'type': 'game_invite',
                        'from_user': {
                            'id': sender.id,
                            'username': sender.username,
                            'display_name': getattr(sender.profile, 'display_name', '')
                        },
                        'game_id': game_id,
                        'message': msg
                    }
                }
            )
        return True
    except User.DoesNotExist:
        return False

# Icebreaker prompts
TRUTH_PROMPTS = [
    "What makes you happy instantly?",
    "What is your comfort movie?",
    "One goal you have this year?",
]
DARE_PROMPTS = [
    "Change your voice and say hi",
    "Sing your favorite song for 5 seconds",
    "Act like a news reporter for 10 seconds",
]
EMOTIONS = ["happy", "jealous", "shy", "excited", "confused", "nervous"]
RAPID_FIRE = [
    "Tea or Coffee?",
    "Love or Career?",
    "Morning or Night?",
    "Cats or Dogs?",
    "Beach or Mountains?",
]
SOUNDS = ["rain", "train", "baby cry", "pressure cooker", "temple bell", "keyboard typing"]
EMOJI_STORIES = [
    ["😀", "🚗", "🌧️"],
    ["🎤", "💔", "🌃"],
    ["📚", "☕", "🚌"],
]
WOULD_YOU_RATHER = [
    "Love marriage or arranged marriage?",
    "Fame or peace?",
    "Travel the world or build your dream home?",
]
COMPLIMENTS = [
    "Compliment their voice",
    "Compliment their smile",
    "Compliment their vibe",
]
ROLE_PLAY_SCENES = [
    "First meeting at bus stop",
    "Old friends after years",
    "Strangers who lost a ticket",
]
MOVIE_SONG = [
    "Act a famous movie scene (no names!)",
    "Hum a song and let them guess",
    "Describe a movie plot in 10 words",
]

def get_icebreaker_prompt(kind: str):
    k = kind.lower()
    if k == "truth":
        return {"type": "truth", "prompt": random.choice(TRUTH_PROMPTS)}
    if k == "dare":
        return {"type": "dare", "prompt": random.choice(DARE_PROMPTS)}
    if k == "truth_or_dare":
        if random.random() < 0.5:
            return {"type": "truth", "prompt": random.choice(TRUTH_PROMPTS)}
        else:
            return {"type": "dare", "prompt": random.choice(DARE_PROMPTS)}
    if k == "guess_emotion":
        return {"type": "guess_emotion", "prompt": random.choice(EMOTIONS)}
    if k == "rapid_fire":
        # select 10 unique questions (or fewer if list small)
        qs = random.sample(RAPID_FIRE, min(10, len(RAPID_FIRE)))
        return {"type": "rapid_fire", "questions": qs, "time_seconds": 5}
    if k == "guess_sound":
        return {"type": "guess_sound", "sound": random.choice(SOUNDS)}
    if k == "emoji_story":
        return {"type": "emoji_story", "emojis": random.choice(EMOJI_STORIES)}
    if k == "would_you_rather":
        return {"type": "would_you_rather", "question": random.choice(WOULD_YOU_RATHER)}
    if k == "two_truths_one_lie":
        return {"type": "two_truths_one_lie", "instructions": "Say 3 statements: 2 truths, 1 lie"}
    if k == "guess_movie_song":
        return {"type": "guess_movie_song", "prompt": random.choice(MOVIE_SONG)}
    if k == "compliment_challenge":
        return {"type": "compliment_challenge", "prompt": random.choice(COMPLIMENTS)}
    if k == "role_play":
        return {"type": "role_play", "scene": random.choice(ROLE_PLAY_SCENES)}
    return {"type": "unknown", "prompt": "Unsupported icebreaker"}

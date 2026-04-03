from ...models import Game
import random

def list_active_games():
    return Game.objects.filter(is_active=True).order_by('name')

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

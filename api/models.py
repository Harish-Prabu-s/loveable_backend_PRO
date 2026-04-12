from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from decimal import Decimal

# ── Hashtag System ──────────────────────────────────────────────────────────

class Hashtag(models.Model):
    name = models.CharField(max_length=100, unique=True)
    usage_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.name}"


# ── Audio Library ────────────────────────────────────────────────────────────

class Audio(models.Model):
    title = models.CharField(max_length=255, default='Original Audio')
    artist = models.CharField(max_length=255, null=True, blank=True)
    file_url = models.FileField(upload_to='audios/')
    cover_image_url = models.URLField(max_length=500, null=True, blank=True)
    duration_ms = models.IntegerField(default=0)
    is_trending = models.BooleanField(default=False)
    language = models.CharField(max_length=50, default='English') # Tamil, English, etc.
    category = models.CharField(max_length=50, default='Trending') # Trending, Pop, Gana, etc.
    shazam_id = models.CharField(max_length=100, null=True, blank=True)
    external_id = models.CharField(max_length=500, null=True, blank=True) # Spotify/YT ID
    is_cached = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_audios')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} by {self.artist or 'Unknown'}"

class FavoriteAudio(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_audios')
    audio = models.ForeignKey(Audio, on_delete=models.CASCADE, related_name='favorited_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'audio')


# ── Social Media Models ──────────────────────────────────────────────────────

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_posts')
    caption = models.TextField(blank=True)
    image = models.ImageField(upload_to='posts/', null=True, blank=True)
    visibility = models.CharField(max_length=20, default='all')
    mentions = models.ManyToManyField(User, related_name='mentioned_in_posts', blank=True)
    audio = models.ForeignKey(Audio, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    hashtags = models.ManyToManyField(Hashtag, related_name='posts', blank=True)
    cover_image = models.ImageField(upload_to='posts/covers/', null=True, blank=True)
    reposted_from = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reposts')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Post by {self.user.username} at {self.created_at}"

class PostLike(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

class PostComment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_post_comments', blank=True)
    mentions = models.ManyToManyField(User, related_name='mentioned_in_post_comments', blank=True)

class Profile(models.Model):
    GENDER_CHOICES = (
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, unique=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    is_busy = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    display_name = models.CharField(max_length=120, default='User', unique=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='profiles/', null=True, blank=True)
    device_token = models.CharField(max_length=255, null=True, blank=True)
    interests = models.JSONField(default=list, blank=True)
    age = models.IntegerField(null=True, blank=True)
    location = models.CharField(max_length=120, null=True, blank=True)
    language = models.CharField(max_length=10, default='en')
    app_lock_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class OTP(models.Model):
    phone_number = models.CharField(max_length=20)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

class EmailOTP(models.Model):
    email = models.EmailField()
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

class PushToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='push_tokens')
    expo_token = models.CharField(max_length=255)
    device = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    coin_balance = models.IntegerField(default=0)
    money_balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_earned = models.IntegerField(default=0)
    total_spent = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

class UserSetting(models.Model):
    APP_LOCK_CHOICES = (
        ('none', 'None'),
        ('pin', 'PIN'),
        ('pattern', 'Pattern'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='settings')
    theme = models.CharField(max_length=20, default='system')
    call_preference = models.CharField(max_length=20, default='both')
    app_lock_type = models.CharField(max_length=20, choices=APP_LOCK_CHOICES, default='none')
    app_lock_value = models.CharField(max_length=255, blank=True)
    notifications_enabled = models.BooleanField(default=True)
    receive_offline_calls = models.BooleanField(default=True)
    biometrics_enabled = models.BooleanField(default=False)
    face_unlock_enabled = models.BooleanField(default=False)
    face_registration_data = models.JSONField(null=True, blank=True)
    fingerprint_registration_data = models.JSONField(null=True, blank=True)

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='performed_notifications')
    notification_type = models.CharField(max_length=50)
    message = models.TextField(blank=True)
    object_id = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class LeagueStats(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='league_stats')
    bet_match_wins = models.IntegerField(default=0)
    total_coins_earned = models.IntegerField(default=0)
    total_money_earned = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_calls_received = models.IntegerField(default=0)
    total_call_seconds = models.IntegerField(default=0)
    total_video_seconds = models.IntegerField(default=0)
    total_audio_seconds = models.IntegerField(default=0)
    monthly_video_seconds = models.IntegerField(default=0)
    monthly_audio_seconds = models.IntegerField(default=0)
    last_reset_month = models.IntegerField(default=0)
    longest_call_seconds = models.IntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

class BetMatch(models.Model):
    male_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bet_matches_as_male')
    female_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='bet_matches_as_female')
    status = models.CharField(max_length=20, default='pending')
    winner_gender = models.CharField(max_length=1, null=True, blank=True)
    result_coins = models.IntegerField(default=0)
    result_money = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    ended_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

class MonetizationRule(models.Model):
    action_type = models.CharField(max_length=50, unique=True)
    cost_per_minute = models.IntegerField(default=0)
    cost_per_message = models.IntegerField(default=0)
    cost_per_media = models.IntegerField(default=0)
    night_cost_multiplier = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal('1.00'))
    reward_male = models.IntegerField(default=0)
    reward_female = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_active = models.BooleanField(default=True)

class CoinTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='transactions')
    type = models.CharField(max_length=10)  # credit/debit
    transaction_type = models.CharField(max_length=20)  # purchase/spent/earned/withdrawal
    amount = models.IntegerField()
    description = models.CharField(max_length=255)
    target_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='involved_transactions')
    created_at = models.DateTimeField(auto_now_add=True)

class DeletionRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reason = models.TextField()
    token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_confirmed = models.BooleanField(default=False)

class Payment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='INR')
    razorpay_order_id = models.CharField(max_length=100)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')  # pending/completed/failed
    coins_added = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class Withdrawal(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.IntegerField()
    account_number = models.CharField(max_length=30)
    ifsc_code = models.CharField(max_length=20)
    account_holder_name = models.CharField(max_length=120)
    status = models.CharField(max_length=20, default='pending')  # pending/approved/rejected
    created_at = models.DateTimeField(auto_now_add=True)

class Game(models.Model):
    CATEGORY_CHOICES = (
        ('LUDO', 'Ludo'),
        ('CARROM', 'Carrom'),
        ('FRUIT', 'Fruit Cutting'),
        ('MATCH3', 'Match 3'),
    )
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

class GameSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game = models.ForeignKey(Game, on_delete=models.CASCADE)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)
    result = models.CharField(max_length=50, null=True, blank=True)
    score = models.IntegerField(default=0)
    coins_spent = models.IntegerField(default=0)

class Gift(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50)  # emoji or icon name
    cost = models.IntegerField(default=10)
    created_at = models.DateTimeField(auto_now_add=True)

class GiftTransaction(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_gifts')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_gifts')
    gift = models.ForeignKey(Gift, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

class LevelProgress(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='levels')
    level = models.IntegerField(default=1)
    xp = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

class Badge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=200, blank=True)
    earned_at = models.DateTimeField(null=True, blank=True)

class DailyReward(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    day = models.IntegerField()
    xp_reward = models.IntegerField(default=0)
    coin_reward = models.IntegerField(default=0)
    claimed_at = models.DateTimeField(null=True, blank=True)
    streak = models.IntegerField(default=0)

class Offer(models.Model):
    TYPE_CHOICES = (
        ('coin_package', 'Coin Package'),
        ('discount', 'Discount'),
        ('bundle', 'Bundle'),
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    offer_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='coin_package')
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=10, default='INR')
    coins_awarded = models.IntegerField(default=0)
    
    gender_target = models.CharField(max_length=1, choices=Profile.GENDER_CHOICES, null=True, blank=True)
    level_min = models.IntegerField(default=1)
    discount_coins = models.IntegerField(default=0)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

class LeagueTier(models.Model):
    name = models.CharField(max_length=50)
    min_points = models.IntegerField(default=0)
    max_points = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class CallSession(models.Model):
    CALL_TYPE_CHOICES = (
        ('VOICE', 'Voice'),
        ('VIDEO', 'Video'),
        ('LIVE', 'Live'),
    )
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls_made')
    callee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='calls_received', null=True, blank=True)
    participants = models.ManyToManyField(User, related_name='active_calls_participated', blank=True)
    is_group = models.BooleanField(default=False)
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES)
    room_id = models.CharField(max_length=50, null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    coins_per_min = models.IntegerField(default=0)
    coins_spent = models.IntegerField(default=0)
    started_at = models.DateTimeField(default=timezone.now)
    ended_at = models.DateTimeField(null=True, blank=True)

class Room(models.Model):
    CALL_TYPE_CHOICES = (
        ('audio', 'Audio'),
        ('video', 'Video'),
    )
    caller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms_started')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms_received', null=True, blank=True)
    call_type = models.CharField(max_length=10, choices=CALL_TYPE_CHOICES)
    status = models.CharField(max_length=10, default='pending')  # pending/active/ended
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    coins_spent = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    chat_theme = models.CharField(max_length=20, default='default') # default, heart, moon, rainbow, boy, couples
    disappearing_messages_enabled = models.BooleanField(default=False)
    disappearing_timer = models.IntegerField(default=0) # 0 means off, otherwise in seconds
    is_archived = models.BooleanField(default=False)
    
    # Group Chat Extension
    is_group = models.BooleanField(default=False)
    name = models.CharField(max_length=100, null=True, blank=True)
    group_avatar = models.URLField(null=True, blank=True)


class Message(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    type = models.CharField(max_length=50, default='text')
    media_url = models.URLField(null=True, blank=True)
    duration_seconds = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    is_seen = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies')

class RoomMember(models.Model):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('member', 'Member'),
    )
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='members')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'user')

class MessageSeen(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='seen_by_users')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user')

class MessageReaction(models.Model):
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    emoji = models.CharField(max_length=50) # store emoji or symbol key
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('message', 'user', 'emoji')


class Streak(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='streaks_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='streaks_user2')
    streak_count = models.IntegerField(default=0)
    last_interaction_date = models.DateTimeField(null=True, blank=True)
    last_uploader = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='streaks_last_uploader')
    freezes_available = models.IntegerField(default=0)

    class Meta:
        unique_together = ('user1', 'user2')

class StreakUpload(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='streak_uploads')
    media_url = models.FileField(upload_to='streaks/', null=True, blank=True)
    media_type = models.CharField(max_length=10, default='image')
    caption = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='all')
    mentions = models.ManyToManyField(User, related_name='mentioned_in_streaks', blank=True)
    audio = models.ForeignKey(Audio, on_delete=models.SET_NULL, null=True, blank=True, related_name='streak_uploads')
    hashtags = models.ManyToManyField(Hashtag, related_name='streak_uploads', blank=True)
    reposted_from = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reposts')
    created_at = models.DateTimeField(auto_now_add=True)

class StreakComment(models.Model):
    streak_upload = models.ForeignKey(StreakUpload, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_streak_comments', blank=True)
    mentions = models.ManyToManyField(User, related_name='mentioned_in_streak_comments', blank=True)

class StreakLike(models.Model):
    streak_upload = models.ForeignKey(StreakUpload, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('streak_upload', 'user')

class StreakReaction(models.Model):
    REACTION_TYPES = (
        ('fire', 'Fire'),
    )
    streak_upload = models.ForeignKey(StreakUpload, on_delete=models.CASCADE, related_name='reactions', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_reactions', null=True)
    reaction_type = models.CharField(max_length=10, choices=REACTION_TYPES, default='fire')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('streak_upload', 'user', 'recipient', 'reaction_type')


class Report(models.Model):
    REASON_CHOICES = (
        ('abuse', 'Abuse/Harassment'),
        ('nudity', 'Nudity/Inappropriate Content'),
        ('spam', 'Spam/Scam'),
        ('other', 'Other'),
    )
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_made')
    reported_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reports_received')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

class Follow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
    following = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'following')

class FollowRequest(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_follow_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_follow_requests')
    status = models.CharField(max_length=20, default='pending')  # pending/accepted/rejected
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

class FriendRequest(models.Model):
    from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
    to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
    status = models.CharField(max_length=20, default='pending')  # pending/accepted/rejected
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('from_user', 'to_user')

class CloseFriend(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='close_friends')
    close_friend = models.ForeignKey(User, on_delete=models.CASCADE, related_name='close_friended_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'close_friend')

class Story(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stories')
    media_url = models.FileField(upload_to='stories/', null=True, blank=True)
    media_type = models.CharField(max_length=10, default='image') # 'image' or 'video'
    caption = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='all')
    mentions = models.ManyToManyField(User, related_name='mentioned_in_stories', blank=True)
    audio = models.ForeignKey(Audio, on_delete=models.SET_NULL, null=True, blank=True, related_name='stories')
    hashtags = models.ManyToManyField(Hashtag, related_name='stories', blank=True)
    reposted_from = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reposts')
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Story by {self.user.username} at {self.created_at}"

class StoryView(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'viewer')

class Reel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reels')
    video_url = models.FileField(upload_to='reels/')
    thumbnail = models.ImageField(upload_to='reels/thumbnails/', null=True, blank=True)
    cover_image = models.ImageField(upload_to='reels/covers/', null=True, blank=True)
    caption = models.TextField(blank=True)
    visibility = models.CharField(max_length=20, default='all')
    mentions = models.ManyToManyField(User, related_name='mentioned_in_reels', blank=True)
    audio = models.ForeignKey(Audio, on_delete=models.SET_NULL, null=True, blank=True, related_name='reels')
    hashtags = models.ManyToManyField(Hashtag, related_name='reels', blank=True)
    reposted_from = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='reposts')
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reel by {self.user.username} at {self.created_at}"

class ReelLike(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('reel', 'user')

class ReelComment(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_reel_comments', blank=True)
    mentions = models.ManyToManyField(User, related_name='mentioned_in_reel_comments', blank=True)

class PostView(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('post', 'viewer')

class ReelView(models.Model):
    reel = models.ForeignKey(Reel, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('reel', 'viewer')

class StreakView(models.Model):
    streak_upload = models.ForeignKey(StreakUpload, on_delete=models.CASCADE, related_name='views')
    viewer = models.ForeignKey(User, on_delete=models.CASCADE)
    viewed_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('streak_upload', 'viewer')

class StoryLike(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('story', 'user')

class StoryComment(models.Model):
    story = models.ForeignKey(Story, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    likes = models.ManyToManyField(User, related_name='liked_story_comments', blank=True)
    mentions = models.ManyToManyField(User, related_name='mentioned_in_story_comments', blank=True)


# ── Highlights System ───────────────────────────────────────────────────────

class Highlight(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlights')
    title = models.CharField(max_length=50, default='Highlight')
    cover_image = models.ImageField(upload_to='highlights/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Highlight: {self.title} by {self.user.username}"

class HighlightStory(models.Model):
    highlight = models.ForeignKey(Highlight, on_delete=models.CASCADE, related_name='stories')
    story = models.ForeignKey(Story, on_delete=models.CASCADE)
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        unique_together = ('highlight', 'story')


# ── Collections (Saved) System ──────────────────────────────────────────────

class Collection(models.Model):
    COLLECTION_TYPES = (
        ('post', 'Posts'),
        ('reel', 'Reels'),
        ('audio', 'Audio'),
        ('general', 'General'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='collections')
    name = models.CharField(max_length=120, default='Saved Items')
    type = models.CharField(max_length=20, choices=COLLECTION_TYPES, default='general')
    is_private = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.type}) for {self.user.username}"

class SavedItem(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
    # Using specific fields for simplicity vs GenericForeignKey in this scale
    post = models.ForeignKey('Post', on_delete=models.CASCADE, null=True, blank=True)
    reel = models.ForeignKey('Reel', on_delete=models.CASCADE, null=True, blank=True)
    audio = models.ForeignKey('Audio', on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('collection', 'post', 'reel', 'audio')

# ----------------------------------------------------------------------------
# SOCIAL GAME ENGINE MODELS
# ----------------------------------------------------------------------------

class QuestionBank(models.Model):
    TYPE_CHOICES = (
        ('truth', 'Truth'),
        ('dare', 'Dare'),
        ('challenge', 'Challenge'),
    )
    question_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    text = models.TextField()
    difficulty = models.IntegerField(default=1) # 1=Easy, 2=Medium, 3=Hard
    category = models.CharField(max_length=50, default='general')
    safety_level = models.CharField(max_length=20, default='safe') # safe, mature, intimate
    
    def __str__(self):
        return f"[{self.question_type}] {self.text[:30]}"

class RelationshipGraph(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rel_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rel_user2')
    interaction_score = models.IntegerField(default=0)
    relationship_tier = models.CharField(max_length=50, default='acquaintance')
    
    class Meta:
        unique_together = ('user1', 'user2')

class MatchmakingQueue(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='match_queue_entry')
    mode = models.CharField(max_length=20, default='2p') # 2p, 4p
    gender = models.CharField(max_length=1) # M, F, O
    game_type = models.CharField(max_length=50, default='all') # truth_or_dare, ludo, card, spin
    joined_at = models.DateTimeField(auto_now_add=True)
    
class GameRoom(models.Model):
    ROOM_TYPE_CHOICES = (
        ('couple', 'Couple'),
        ('group', 'Group'),
        ('random', 'Random'),
    )
    MODE_CHOICES = (
        ('truth_dare', 'Truth or Dare'),
        ('romantic', 'Romantic Connection'),
        ('deep', 'Deep Questions'),
        ('flirty', 'Flirty Challenge'),
        ('roleplay', 'Roleplay Lite'),
        ('memory', 'Memory Meter'),
        ('draw_guess', 'Draw & Guess'),
        ('coop', 'Co-op Task'),
        ('random_match', 'Random Match'),
    )
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_games', null=True, blank=True)
    room_code = models.CharField(max_length=10, unique=True, null=True, blank=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPE_CHOICES, default='group')
    game_mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='truth_dare')
    status = models.CharField(max_length=20, default='lobby') # lobby, waiting, in_progress, ended
    created_at = models.DateTimeField(auto_now_add=True)

class InteractiveGameSession(models.Model):
    room = models.ForeignKey(GameRoom, on_delete=models.CASCADE, related_name='game_sessions', null=True)
    current_state = models.CharField(max_length=50, default='Waiting') # Waiting, TurnAssigned, ActionPending, VotingState, ResultState, EndState
    current_turn_player = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='active_turns')
    round_number = models.IntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    active_prompt = models.ForeignKey(QuestionBank, null=True, blank=True, on_delete=models.SET_NULL)
    action_payload = models.JSONField(null=True, blank=True) # e.g. what the user submitted (image/text)
    votes_pass = models.IntegerField(default=0)
    votes_fail = models.IntegerField(default=0)
    
    # Truth or Dare Specific
    current_questioner_player = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='active_questions')
    timer_started_at = models.DateTimeField(null=True, blank=True)
    selected_option = models.CharField(max_length=10, null=True, blank=True) # 'truth' or 'dare'
    turn_history = models.JSONField(default=list, blank=True)

    
class PlayerState(models.Model):
    session = models.ForeignKey(InteractiveGameSession, on_delete=models.CASCADE, related_name='players')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    is_connected = models.BooleanField(default=False)
    score = models.IntegerField(default=0)
    hidden_role = models.CharField(max_length=50, null=True, blank=True) # Imposter, innocent, etc.

class GameEventLog(models.Model):
    session = models.ForeignKey(InteractiveGameSession, on_delete=models.CASCADE, related_name='logs')
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    event_type = models.CharField(max_length=50) # PlayerJoined, GameStarted, TurnAssigned, VoteCast, etc
    payload = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)

class MatchmakingLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    mode = models.CharField(max_length=50) # e.g. truth_or_dare_2p
    status = models.CharField(max_length=20) # searched, matched, cancelled, timeout
    is_expanded = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

class UserRelationship(models.Model):
    user_one = models.ForeignKey(User, on_delete=models.CASCADE, related_name='relationships_initiated')
    user_two = models.ForeignKey(User, on_delete=models.CASCADE, related_name='relationships_accepted')
    closeness_score = models.IntegerField(default=0)
    streak_count = models.IntegerField(default=0)
    last_interaction = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user_one', 'user_two')


# ── Notes Feature ───────────────────────────────────────────────────────────

class Note(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='note')
    text = models.CharField(max_length=60, blank=True)
    audio = models.ForeignKey(Audio, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    mentions = models.ManyToManyField(User, related_name='mentioned_in_notes', blank=True)
    audio_start_sec = models.IntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Note by {self.user.username}: {self.text[:30]}"

class NoteLike(models.Model):
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='likes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('note', 'user')


# ── Multi-Image Posts ────────────────────────────────────────────────────────

class PostImage(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='posts/')
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Image #{self.order} for Post #{self.post_id}"

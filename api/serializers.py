from django.contrib.auth.models import User
from rest_framework import serializers
from django.conf import settings
from django.utils import timezone
from .models import (
    Profile, Wallet, CoinTransaction, Payment, Withdrawal,
    Game, LevelProgress, Offer, LeagueTier, CallSession,
    Badge, DailyReward, Room, Message, Story, Gift, GiftTransaction, StoryView, Follow, Reel, Streak, Post, PostLike,
    CloseFriend, PostView, ReelView, StreakView, StreakUpload, MessageReaction, Note,
    Highlight, HighlightStory, Collection, SavedItem, FavoriteAudio
)
from .utils import get_absolute_media_url
from .models import Audio

class AudioSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    cover_image_url = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    
    class Meta:
        model = Audio
        fields = ['id', 'title', 'artist', 'file_url', 'cover_image_url', 'duration_ms', 'is_trending', 'language', 'category', 'is_favorite']

    def get_is_favorite(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return FavoriteAudio.objects.filter(user=request.user, audio=obj).exists()
        return False

    def get_file_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.file_url, request)

    def get_cover_image_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.cover_image_url, request)

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'last_login', 'date_joined']

class SimpleUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    gender = serializers.CharField(source='profile.gender', read_only=True)
    user_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'user_id', 'username', 'display_name', 'photo', 'gender']

    def get_display_name(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile and profile.display_name and profile.display_name != 'User':
            return profile.display_name
        
        # Fallback to sanitized username if display_name is default/missing
        if obj.username.startswith('user_'):
            return "User" # Hide the mobile number if it's the auto-generated username
        return obj.username or "User"

    def get_photo(self, obj):
        request = self.context.get('request')
        profile = getattr(obj, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None


class WalletSerializer(serializers.ModelSerializer):
    has_purchased = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'user', 'coin_balance', 'total_earned', 'total_spent', 'updated_at', 'has_purchased']

    def get_has_purchased(self, obj):
        return obj.transactions.filter(transaction_type='purchase').exists()

class CoinTransactionSerializer(serializers.ModelSerializer):
    actor_display_name = serializers.SerializerMethodField()

    class Meta:
        model = CoinTransaction
        fields = ['id', 'wallet', 'type', 'transaction_type', 'amount', 'description', 'created_at', 'actor_display_name']

    def get_actor_display_name(self, obj):
        if obj.target_user:
            profile = getattr(obj.target_user, 'profile', None)
            return profile.display_name if profile else obj.target_user.username
        return None

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'user', 'amount', 'currency', 'razorpay_order_id', 'razorpay_payment_id', 'razorpay_signature', 'status', 'coins_added', 'created_at']

class WithdrawalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Withdrawal
        fields = ['id', 'user', 'amount', 'account_number', 'ifsc_code', 'account_holder_name', 'status', 'created_at']

class GameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Game
        fields = ['id', 'name', 'category', 'is_active', 'created_at']

class LevelProgressSerializer(serializers.ModelSerializer):
    class Meta:
        model = LevelProgress
        fields = ['id', 'user', 'level', 'xp', 'last_updated']

class OfferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Offer
        fields = ['id', 'title', 'description', 'offer_type', 'price', 'currency', 'coins_awarded', 'gender_target', 'level_min', 'discount_coins', 'start_time', 'end_time', 'is_active']

class LeagueTierSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeagueTier
        fields = ['id', 'name', 'min_points', 'max_points', 'created_at']

class CallSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CallSession
        fields = ['id', 'caller', 'callee', 'call_type', 'duration_seconds', 'coins_per_min', 'coins_spent', 'started_at', 'ended_at']

class BadgeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Badge
        fields = ['id', 'user', 'name', 'description', 'icon', 'earned_at']

class DailyRewardSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReward
        fields = ['id', 'user', 'day', 'xp_reward', 'coin_reward', 'claimed_at', 'streak']

class RoomSerializer(serializers.ModelSerializer):
    caller_profile = SimpleUserSerializer(source='caller', read_only=True)
    receiver_profile = SimpleUserSerializer(source='receiver', read_only=True)
    group_avatar = serializers.SerializerMethodField()
    collage_photos = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = ['id', 'caller', 'receiver', 'caller_profile', 'receiver_profile', 'call_type', 'status', 'started_at', 'ended_at', 'duration_seconds', 'coins_spent', 'created_at', 'chat_theme', 'disappearing_messages_enabled', 'disappearing_timer', 'is_group', 'name', 'group_avatar', 'collage_photos', 'is_archived']

    def get_group_avatar(self, obj):
        request = self.context.get('request')
        if obj.group_avatar:
            return get_absolute_media_url(obj.group_avatar, request)
        return None

    def get_collage_photos(self, obj):
        if not obj.is_group:
            return []
        
        request = self.context.get('request')
        from django.contrib.auth.models import User
        # Get last 4 unique senders from messages
        sender_ids = obj.messages.order_by('-created_at').values_list('sender_id', flat=True)
        seen = set()
        photos = []
        for sid in sender_ids:
            if sid not in seen:
                seen.add(sid)
                try:
                    user = User.objects.get(id=sid)
                    if user.profile and user.profile.photo:
                        photos.append(get_absolute_media_url(user.profile.photo, request))
                except:
                    pass
            if len(photos) >= 4:
                break
        return photos

class MessageReactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageReaction
        fields = ['id', 'user', 'emoji', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    reply_to = serializers.SerializerMethodField()
    reactions = MessageReactionSerializer(many=True, read_only=True)
    
    class Meta:
        model = Message
        fields = ['id', 'room', 'sender', 'content', 'type', 'media_url', 'duration_seconds', 'created_at', 'is_seen', 'seen_at', 'expires_at', 'reply_to', 'reactions']

    def get_reply_to(self, obj):
        if obj.reply_to:
            return {
                'id': obj.reply_to.id,
                'content': obj.reply_to.content,
                'type': obj.reply_to.type,
                'sender': obj.reply_to.sender.id,
                'created_at': obj.reply_to.created_at
            }
        return None

class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ['id', 'user1', 'user2', 'streak_count', 'last_interaction_date', 'freezes_available']

class StorySerializer(serializers.ModelSerializer):
    user_display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    view_count = serializers.IntegerField(source='views.count', read_only=True)
    media_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)
    audio_details = AudioSerializer(source='audio', read_only=True)

    reposted_from = serializers.PrimaryKeyRelatedField(read_only=True)
    parent_user = SimpleUserSerializer(source='reposted_from.user', read_only=True)

    class Meta:
        model = Story
        fields = ['id', 'user', 'media_url', 'media_type', 'caption', 'created_at', 'expires_at', 'user_display_name', 'user_username', 'user_avatar', 'view_count', 'likes_count', 'comments_count', 'is_liked', 'is_owner', 'mentioned_users', 'reposted_from', 'parent_user', 'audio_details']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_media_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.media_url, request)

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class StoryViewSerializer(serializers.ModelSerializer):
    viewer_name = serializers.CharField(source='viewer.profile.display_name', read_only=True)
    viewer_avatar = serializers.SerializerMethodField()

    class Meta:
        model = StoryView
        fields = ['id', 'viewer', 'viewer_name', 'viewer_avatar', 'viewed_at']

    def get_viewer_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.viewer, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class PostViewSerializer(serializers.ModelSerializer):
    viewer_name = serializers.CharField(source='viewer.profile.display_name', read_only=True)
    viewer_avatar = serializers.SerializerMethodField()
    class Meta:
        model = PostView
        fields = ['id', 'viewer', 'viewer_name', 'viewer_avatar', 'viewed_at']
    def get_viewer_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.viewer, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class ReelViewSerializer(serializers.ModelSerializer):
    viewer_name = serializers.CharField(source='viewer.profile.display_name', read_only=True)
    viewer_avatar = serializers.SerializerMethodField()
    class Meta:
        model = ReelView
        fields = ['id', 'viewer', 'viewer_name', 'viewer_avatar', 'viewed_at']
    def get_viewer_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.viewer, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class StreakViewSerializer(serializers.ModelSerializer):
    viewer_name = serializers.CharField(source='viewer.profile.display_name', read_only=True)
    viewer_avatar = serializers.SerializerMethodField()
    class Meta:
        model = StreakView
        fields = ['id', 'viewer', 'viewer_name', 'viewer_avatar', 'viewed_at']
    def get_viewer_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.viewer, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class StreakUploadSerializer(serializers.ModelSerializer):
    user_display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    media_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    view_count = serializers.IntegerField(source='views.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    audio_details = AudioSerializer(source='audio', read_only=True)
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)

    class Meta:
        model = StreakUpload
        fields = [
            'id', 'user', 'user_display_name', 'user_avatar', 'media_url', 'media_type', 
            'caption', 'visibility', 'created_at', 'likes_count', 'comments_count', 
            'view_count', 'is_liked', 'is_owner', 'audio_details', 'mentioned_users'
        ]

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile: return get_absolute_media_url(profile.photo, request)
        return None

    def get_media_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.media_url, request)

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

class ReelSerializer(serializers.ModelSerializer):
    user_display_name = serializers.SerializerMethodField()
    user_username = serializers.CharField(source='user.username', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    view_count = serializers.IntegerField(source='views.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)
    audio_details = AudioSerializer(source='audio', read_only=True)

    reposted_from = serializers.PrimaryKeyRelatedField(read_only=True)
    parent_user = SimpleUserSerializer(source='reposted_from.user', read_only=True)

    class Meta:
        model = Reel
        fields = ['id', 'user', 'video_url', 'caption', 'created_at', 'user_display_name', 'user_username', 'user_avatar', 'likes_count', 'comments_count', 'view_count', 'is_liked', 'is_owner', 'is_following', 'mentioned_users', 'reposted_from', 'parent_user', 'audio_details']

    def get_is_owner(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return Follow.objects.filter(follower=request.user, following=obj.user).exists()
        return False

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(user=request.user).exists()
        return False

    def get_video_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.video_url, request)

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

    def get_user_display_name(self, obj):
        profile = getattr(obj.user, 'profile', None)
        if profile:
            return profile.display_name
        return obj.user.username or 'User'

class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ['id', 'name', 'icon', 'cost']

class GiftTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftTransaction
        fields = ['id', 'sender', 'receiver', 'gift', 'created_at']

class ContactSerializer(serializers.Serializer):
    id = serializers.IntegerField() # User ID for 1v1, Room ID for Groups
    username = serializers.CharField(required=False, allow_null=True)
    display_name = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    last_message = serializers.CharField(required=False, allow_null=True)
    last_message_type = serializers.CharField(required=False, allow_null=True)
    last_timestamp = serializers.DateTimeField(required=False, allow_null=True)
    unread_count = serializers.IntegerField(default=0)
    streak_count = serializers.IntegerField(default=0)
    streak_last_interaction = serializers.DateTimeField(required=False, allow_null=True)
    current_note = serializers.SerializerMethodField()
    
    # Group Fields
    is_group = serializers.BooleanField(default=False)
    room_id = serializers.IntegerField()
    name = serializers.CharField(required=False, allow_null=True)
    group_avatar = serializers.CharField(required=False, allow_null=True)
    collage_photos = serializers.SerializerMethodField()

    def get_collage_photos(self, obj):
        if not getattr(obj, 'is_group', False):
            return []
        # obj in ContactSerializer might be a room-like object or user-like
        # We need to get the room and its messages
        try:
            from .models import Room
            room = Room.objects.get(id=obj.room_id)
            return RoomSerializer(context=self.context).get_collage_photos(room)
        except:
            return []

    def get_current_note(self, obj):
        if getattr(obj, 'is_group', False):
            return None
        
        user_id = getattr(obj, 'id', None)
        if not user_id:
            return None
            
        try:
            from .models import Note
            note = Note.objects.filter(user_id=user_id).first()
            if note and (not note.expires_at or note.expires_at > timezone.now()):
                return {
                    'text': note.text,
                    'audio_title': note.audio.title if note.audio else None,
                    'audio_url': get_absolute_media_url(note.audio.file_url, self.context.get('request')) if note.audio else None,
                    'created_at': note.created_at
                }
        except:
            pass
        return None

    def get_display_name(self, obj):
        if getattr(obj, 'is_group', False):
            return getattr(obj, 'name', 'Group')
        profile = getattr(obj, 'profile', None)
        return profile.display_name if profile else getattr(obj, 'username', 'User')

    def get_photo(self, obj):
        request = self.context.get('request')
        if getattr(obj, 'is_group', False):
            return get_absolute_media_url(getattr(obj, 'group_avatar', None), request)
        profile = getattr(obj, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class PostSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(source='user.profile.id', read_only=True)
    display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    photo = serializers.SerializerMethodField()
    gender = serializers.CharField(source='user.profile.gender', read_only=True)
    image = serializers.SerializerMethodField()
    caption = serializers.CharField()
    image = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    view_count = serializers.IntegerField(source='views.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    aspect_ratio = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    audio_details = AudioSerializer(source='audio', read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'user', 'profile_id', 'display_name', 'username', 'photo', 'gender',
            'caption', 'image', 'images', 'likes_count', 'comments_count', 'view_count', 'is_liked', 'is_owner',
            'created_at', 'mentioned_users', 'reposted_from', 'parent_user', 'aspect_ratio', 'audio_details'
        ]
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)
    reposted_from = serializers.PrimaryKeyRelatedField(read_only=True)
    parent_user = SimpleUserSerializer(source='reposted_from.user', read_only=True)

    def get_photo(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

    def get_image(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.image, request)

    def get_is_liked(self, obj):
        request = self.context.get('request')
        user = None
        if request and request.user.is_authenticated:
            user = request.user
        else:
            user = self.context.get('request_user')
            
        if user:
            return PostLike.objects.filter(post=obj, user=user).exists()
        return False

    def get_is_owner(self, obj):
        request = self.context.get('request')
        user = None
        if request and request.user.is_authenticated:
            user = request.user
        else:
            user = self.context.get('request_user')
            
        if user:
            return obj.user == user
        return False

    def get_aspect_ratio(self, obj):
        if not obj.image:
            return 1.0
        try:
            return obj.image.width / obj.image.height
        except Exception:
            return 1.0

    def get_images(self, obj):
        request = self.context.get('request')
        imgs = []
        if obj.image:
            imgs.append(get_absolute_media_url(obj.image, request))
        
        from .models import PostImage
        post_imgs = PostImage.objects.filter(post=obj).order_by('order')
        for pi in post_imgs:
            if pi.image:
                imgs.append(get_absolute_media_url(pi.image, request))
        return imgs

class HighlightStorySerializer(serializers.ModelSerializer):
    story = StorySerializer(read_only=True)
    class Meta:
        model = HighlightStory
        fields = ['id', 'story', 'order']

class HighlightSerializer(serializers.ModelSerializer):
    stories = HighlightStorySerializer(many=True, read_only=True)
    cover_image = serializers.SerializerMethodField()

    class Meta:
        model = Highlight
        fields = ['id', 'user', 'title', 'cover_image', 'stories', 'created_at']
        read_only_fields = ['user']

    def get_cover_image(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.cover_image, request)

class SavedItemSerializer(serializers.ModelSerializer):
    post = PostSerializer(read_only=True)
    reel = ReelSerializer(read_only=True)
    audio = AudioSerializer(read_only=True)

    class Meta:
        model = SavedItem
        fields = ['id', 'post', 'reel', 'audio', 'created_at']

class CollectionSerializer(serializers.ModelSerializer):
    items = SavedItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = Collection
        fields = ['id', 'name', 'type', 'is_private', 'item_count', 'items', 'created_at']

class CloseFriendSerializer(serializers.ModelSerializer):
    close_friend = SimpleUserSerializer()

    class Meta:
        model = CloseFriend
        fields = ['id', 'close_friend', 'created_at']

class ProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    is_following = serializers.SerializerMethodField()
    is_close_friend = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    friend_request_status = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    is_busy = serializers.SerializerMethodField()
    phone_number = serializers.SerializerMethodField()
    email = serializers.EmailField(read_only=True)
    highlights = HighlightSerializer(many=True, read_only=True)

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'username', 'phone_number', 'gender', 'is_verified', 'is_online', 'is_busy',
            'date_joined', 'last_login', 'email', 'display_name', 'bio', 'photo',
            'interests', 'age', 'location', 'language', 'app_lock_enabled',
            'created_at', 'updated_at', 'is_following', 'is_close_friend', 'followers_count', 'following_count',
            'friend_request_status', 'highlights'
        ]

    def get_is_busy(self, obj):
        from .modules.chat.services import presence_status
        return presence_status(obj.user.id) == 'busy'

    def get_phone_number(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.user == request.user:
            return obj.phone_number
        return None

    def get_email(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.user == request.user:
            return obj.email
        return None

    def get_photo(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.photo, request)

    def get_is_following(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Check if Follow model exists and check relation
            return Follow.objects.filter(follower=request.user, following=obj.user).exists()
        return False

    def get_is_close_friend(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CloseFriend.objects.filter(user=request.user, close_friend=obj.user).exists()
        return False

    def get_followers_count(self, obj):
        return Follow.objects.filter(following=obj.user).count()

    def get_following_count(self, obj):
        return Follow.objects.filter(follower=obj.user).count()

    def get_friend_request_status(self, obj):
        request = self.context.get('request')
        if request and getattr(request, 'user', None) and request.user.is_authenticated:
            try:
                from .models import FriendRequest
                # Case 1: I sent a request to them (return primitives only)
                sent = (FriendRequest.objects
                        .filter(from_user=request.user, to_user=obj.user)
                        .values('id', 'status')
                        .first())
                if sent:
                    return {'status': str(sent['status']), 'direction': 'sent', 'id': int(sent['id'])}
                
                # Case 2: They sent a request to me
                received = (FriendRequest.objects
                            .filter(from_user=obj.user, to_user=request.user)
                            .values('id', 'status')
                            .first())
                if received:
                    return {'status': str(received['status']), 'direction': 'received', 'id': int(received['id'])}
            except Exception:
                return None
        return None
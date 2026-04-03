from django.contrib.auth.models import User
from rest_framework import serializers
from django.conf import settings
from .models import (
    Profile, Wallet, CoinTransaction, Payment, Withdrawal,
    Game, LevelProgress, Offer, LeagueTier, CallSession,
    Badge, DailyReward, Room, Message, Story, Gift, GiftTransaction, StoryView, Follow, Reel, Streak, Post, PostLike,
    CloseFriend
)
from .utils import get_absolute_media_url

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'last_login', 'date_joined']

class SimpleUserSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(source='profile.display_name', read_only=True)
    photo = serializers.SerializerMethodField()
    gender = serializers.CharField(source='profile.gender', read_only=True)
    user_id = serializers.IntegerField(source='id', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'user_id', 'username', 'display_name', 'photo', 'gender']

    def get_photo(self, obj):
        request = self.context.get('request')
        profile = getattr(obj, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class ProfileSerializer(serializers.ModelSerializer):
    is_following = serializers.SerializerMethodField()
    is_close_friend = serializers.SerializerMethodField()
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    friend_request_status = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    is_busy = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'id', 'user', 'phone_number', 'gender', 'is_verified', 'is_online', 'is_busy',
            'date_joined', 'last_login', 'email', 'display_name', 'bio', 'photo',
            'interests', 'age', 'location', 'language', 'app_lock_enabled',
            'created_at', 'updated_at', 'is_following', 'is_close_friend', 'followers_count', 'following_count',
            'friend_request_status'
        ]

    def get_is_busy(self, obj):
        from .modules.chat.services import presence_status
        return presence_status(obj.user.id) == 'busy'

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

class WalletSerializer(serializers.ModelSerializer):
    has_purchased = serializers.SerializerMethodField()

    class Meta:
        model = Wallet
        fields = ['id', 'user', 'coin_balance', 'total_earned', 'total_spent', 'updated_at', 'has_purchased']

    def get_has_purchased(self, obj):
        return obj.transactions.filter(transaction_type='purchase').exists()

class CoinTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CoinTransaction
        fields = ['id', 'wallet', 'type', 'transaction_type', 'amount', 'description', 'created_at']

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
    class Meta:
        model = Room
        fields = ['id', 'caller', 'receiver', 'call_type', 'status', 'started_at', 'ended_at', 'duration_seconds', 'coins_spent', 'created_at', 'chat_theme', 'disappearing_messages_enabled', 'disappearing_timer']

class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = ['id', 'room', 'sender', 'content', 'type', 'media_url', 'duration_seconds', 'created_at', 'is_seen', 'expires_at']

class StreakSerializer(serializers.ModelSerializer):
    class Meta:
        model = Streak
        fields = ['id', 'user1', 'user2', 'streak_count', 'last_interaction_date', 'freezes_available']

class StorySerializer(serializers.ModelSerializer):
    user_display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    view_count = serializers.IntegerField(source='views.count', read_only=True)
    media_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)

    class Meta:
        model = Story
        fields = ['id', 'user', 'media_url', 'media_type', 'caption', 'created_at', 'expires_at', 'user_display_name', 'user_avatar', 'view_count', 'likes_count', 'comments_count', 'is_liked', 'is_owner', 'mentioned_users']

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

class ReelSerializer(serializers.ModelSerializer):
    user_display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    user_avatar = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)

    class Meta:
        model = Reel
        fields = ['id', 'user', 'video_url', 'caption', 'created_at', 'user_display_name', 'user_avatar', 'likes_count', 'comments_count', 'is_liked', 'is_owner', 'mentioned_users']

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

    def get_video_url(self, obj):
        request = self.context.get('request')
        return get_absolute_media_url(obj.video_url, request)

    def get_user_avatar(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class GiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gift
        fields = ['id', 'name', 'icon', 'cost']

class GiftTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftTransaction
        fields = ['id', 'sender', 'receiver', 'gift', 'created_at']

class ContactSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.SerializerMethodField()
    photo = serializers.SerializerMethodField()
    last_message = serializers.CharField()
    last_message_type = serializers.CharField()
    last_timestamp = serializers.DateTimeField()
    unread_count = serializers.IntegerField(default=0)
    streak_count = serializers.IntegerField(default=0)
    streak_last_interaction = serializers.DateTimeField(required=False)

    def get_display_name(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.display_name if profile else obj.username

    def get_photo(self, obj):
        request = self.context.get('request')
        profile = getattr(obj, 'profile', None)
        if profile:
            return get_absolute_media_url(profile.photo, request)
        return None

class PostSerializer(serializers.ModelSerializer):
    profile_id = serializers.IntegerField(source='user.profile.id', read_only=True)
    display_name = serializers.CharField(source='user.profile.display_name', read_only=True)
    username = serializers.CharField(source='user.profile.display_name', read_only=True)
    photo = serializers.SerializerMethodField()
    gender = serializers.CharField(source='user.profile.gender', read_only=True)
    image = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='likes.count', read_only=True)
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'user', 'profile_id', 'display_name', 'username', 'photo', 'gender',
            'caption', 'image', 'likes_count', 'comments_count', 'is_liked', 'is_owner',
            'created_at', 'mentioned_users'
        ]
    mentioned_users = SimpleUserSerializer(source='mentions', many=True, read_only=True)

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

class CloseFriendSerializer(serializers.ModelSerializer):
    close_friend = SimpleUserSerializer()

    class Meta:
        model = CloseFriend
        fields = ['id', 'close_friend', 'created_at']
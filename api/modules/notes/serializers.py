from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from ...models import Note, Profile
from ...utils import get_absolute_media_url

class NoteSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    display_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    likes_count = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'user_id', 'username', 'display_name', 'profile_image',
            'note_type', 'text', 'emoji', 
            'music_id', 'music_title', 'music_artist', 'music_thumbnail', 'music_image',
            'music_url', 'lyrics',
            'is_active', 'created_at', 'updated_at', 'expires_at', 
            'is_mine', 'likes_count', 'is_liked'
        ]

    def get_display_name(self, obj):
        profile = getattr(obj.user, 'profile', None)
        return profile.display_name if profile else obj.user.username

    def get_profile_image(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile and profile.photo:
            return get_absolute_media_url(profile.photo, request)
        return None

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

    def get_likes_count(self, obj):
        if hasattr(obj, 'likes_count'):
            return obj.likes_count
        return obj.likes.count()

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            if hasattr(obj, 'is_liked'):
                return obj.is_liked
            return obj.likes.filter(user=request.user).exists()
        return False

class CreateOrReplaceNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = [
            'note_type', 'text', 'emoji', 
            'music_id', 'music_title', 'music_artist', 'music_thumbnail', 'music_image',
            'music_url', 'lyrics'
        ]

class MyNoteSerializer(NoteSerializer):
    class Meta(NoteSerializer.Meta):
        pass

class ChatRowNoteSerializer(NoteSerializer):
    class Meta(NoteSerializer.Meta):
        pass

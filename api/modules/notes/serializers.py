from rest_framework import serializers
from django.contrib.auth.models import User
from django.utils import timezone
from ...models import Note, Profile
from ...utils import get_absolute_media_url

class NoteUserSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'display_name', 'profile_image']

    def get_display_name(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.display_name if profile else obj.username

    def get_profile_image(self, obj):
        request = self.context.get('request')
        profile = getattr(obj, 'profile', None)
        if profile and profile.photo:
            return get_absolute_media_url(profile.photo, request)
        return None

class NoteSerializer(serializers.ModelSerializer):
    user = NoteUserSerializer(read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Note
        fields = [
            'id', 'user', 'note_type', 'text', 'emoji', 
            'music_id', 'music_title', 'music_artist', 'music_thumbnail',
            'is_active', 'created_at', 'updated_at', 'expires_at', 'is_mine'
        ]

    def get_is_mine(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.user == request.user
        return False

class CreateOrReplaceNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Note
        fields = [
            'note_type', 'text', 'emoji', 
            'music_id', 'music_title', 'music_artist', 'music_thumbnail'
        ]

class MyNoteSerializer(NoteSerializer):
    class Meta(NoteSerializer.Meta):
        pass

class ChatRowNoteSerializer(NoteSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    profile_image = serializers.SerializerMethodField()

    class Meta(NoteSerializer.Meta):
        fields = [
            'id', 'is_mine', 'username', 'profile_image', 'note_type', 
            'text', 'emoji', 'music_title', 'music_artist', 'music_thumbnail',
            'created_at', 'expires_at'
        ]

    def get_profile_image(self, obj):
        request = self.context.get('request')
        profile = getattr(obj.user, 'profile', None)
        if profile and profile.photo:
            return get_absolute_media_url(profile.photo, request)
        return None

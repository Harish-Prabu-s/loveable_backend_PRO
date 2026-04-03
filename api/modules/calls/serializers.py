from rest_framework import serializers
from api.models import CallSession, Room


class CallSessionSerializer(serializers.ModelSerializer):
    caller_name    = serializers.CharField(source='caller.profile.display_name', read_only=True)
    callee_name    = serializers.CharField(source='callee.profile.display_name', read_only=True)
    caller_photo   = serializers.ImageField(source='caller.profile.photo', read_only=True)
    callee_photo   = serializers.ImageField(source='callee.profile.photo', read_only=True)
    caller_online  = serializers.BooleanField(source='caller.profile.is_online', read_only=True)
    callee_online  = serializers.BooleanField(source='callee.profile.is_online', read_only=True)

    class Meta:
        model  = CallSession
        fields = '__all__'
        read_only_fields = ('id', 'started_at', 'ended_at', 'duration_seconds', 'coins_spent')


class RoomSerializer(serializers.ModelSerializer):
    caller_name  = serializers.CharField(source='caller.profile.display_name', read_only=True)
    receiver_name = serializers.CharField(source='receiver.profile.display_name', read_only=True)

    class Meta:
        model  = Room
        fields = '__all__'
        read_only_fields = ('id', 'created_at', 'started_at', 'ended_at', 'duration_seconds', 'coins_spent')

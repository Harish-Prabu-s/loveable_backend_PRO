from rest_framework import serializers

class SocialEventSerializer(serializers.Serializer):
    """
    Serializer for the Blueprint §5.3 Social Intelligence Layer events.
    """
    event_id = serializers.CharField(max_length=64)
    event_type = serializers.CharField(max_length=64)
    target_user_id = serializers.IntegerField()
    source = serializers.JSONField()
    context = serializers.JSONField(required=False, default=dict)
    interaction = serializers.JSONField()
    feed_session_id = serializers.CharField(max_length=64, required=False, allow_null=True)
    timestamp = serializers.DateTimeField()

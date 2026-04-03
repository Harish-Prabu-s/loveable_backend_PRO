from rest_framework import serializers
from api.models import BetMatch
from django.contrib.auth.models import User


class BetMatchSerializer(serializers.ModelSerializer):
    male_user_name   = serializers.CharField(source='male_user.profile.display_name', read_only=True)
    female_user_name = serializers.SerializerMethodField()
    male_user_photo  = serializers.SerializerMethodField()
    female_user_photo = serializers.SerializerMethodField()

    class Meta:
        model  = BetMatch
        fields = '__all__'
        read_only_fields = ('id', 'status', 'winner_gender', 'result_coins', 'result_money', 'created_at', 'ended_at')

    def get_female_user_name(self, obj):
        if obj.female_user:
            try:
                return obj.female_user.profile.display_name
            except Exception:
                return None
        return None

    def get_male_user_photo(self, obj):
        try:
            return str(obj.male_user.profile.photo) if obj.male_user.profile.photo else None
        except Exception:
            return None

    def get_female_user_photo(self, obj):
        if obj.female_user:
            try:
                return str(obj.female_user.profile.photo) if obj.female_user.profile.photo else None
            except Exception:
                return None
        return None

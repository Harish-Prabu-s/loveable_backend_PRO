from rest_framework import serializers
from api.models import MonetizationRule


class MonetizationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = MonetizationRule
        fields = '__all__'
        read_only_fields = ('id', 'created_at')

from rest_framework import serializers


class AckSerializer(serializers.Serializer):
    """Acknowledgement of one alert finding, sent with a prescription/dispense commit."""

    rule_code = serializers.CharField()
    reason = serializers.CharField()
    note = serializers.CharField(required=False, allow_blank=True)
    referral = serializers.BooleanField(required=False, default=False)
    referral_note = serializers.CharField(required=False, allow_blank=True)

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from core.permissions import Roles

from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "phone", "role", "licence_number", "cadre",
            "facility_id", "county_code", "status", "approved_at", "created_at",
        ]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    role = serializers.ChoiceField(choices=[Roles.PRESCRIBER, Roles.PHARMACIST])
    licence_number = serializers.CharField(max_length=30)
    facility_id = serializers.UUIDField()

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value.lower()


class LoginSerializer(TokenObtainPairSerializer):
    """JWT login that also returns the user profile and puts role/facility in the token."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["facility_id"] = str(user.facility_id) if user.facility_id else None
        token["county_code"] = user.county_code
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data

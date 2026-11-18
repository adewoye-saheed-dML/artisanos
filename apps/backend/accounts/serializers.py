from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from organizations.models import Membership, Organization
from organizations.serializers import MembershipSummarySerializer
from organizations.services import create_organization_with_owner

from .models import User


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "phone", "is_platform_admin", "created_at", "memberships"]
        read_only_fields = fields

    @extend_schema_field(MembershipSummarySerializer(many=True))
    def get_memberships(self, obj):
        qs = Membership.objects.select_related("organization").filter(
            user=obj,
            status=Membership.Status.ACTIVE,
            organization__is_active=True,
        )
        return MembershipSummarySerializer(qs, many=True).data


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    # Optional initial workspace creation during onboarding
    organization_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    organization_category = serializers.ChoiceField(
        choices=Organization.Category.choices,
        required=False,
        default=Organization.Category.TAILOR,
    )
    currency = serializers.CharField(max_length=3, required=False, default="NGN")
    preferred_unit = serializers.ChoiceField(
        choices=Organization.UnitSystem.choices,
        required=False,
        default=Organization.UnitSystem.CM,
    )
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_currency(self, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code (e.g. NGN, USD, GBP).")
        return cleaned

    @transaction.atomic
    def create(self, validated_data):
        org_name = validated_data.pop("organization_name", "").strip()
        org_category = validated_data.pop("organization_category", Organization.Category.TAILOR)
        currency = validated_data.pop("currency", "NGN")
        preferred_unit = validated_data.pop("preferred_unit", Organization.UnitSystem.CM)
        city = validated_data.pop("city", "")
        country = validated_data.pop("country", "")

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"].strip(),
            phone=validated_data.get("phone", "").strip(),
        )

        if org_name:
            create_organization_with_owner(
                user=user,
                name=org_name,
                category=org_category,
                currency=currency,
                preferred_unit=preferred_unit,
                city=city,
                country=country,
                email=user.email,
                phone=user.phone,
            )

        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]
        user = authenticate(request=self.context.get("request"), username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

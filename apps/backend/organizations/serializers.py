from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Membership, Organization, OrganizationInvitation
from .services import create_organization_with_owner


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "currency",
            "preferred_unit",
            "is_active",
            "created_at",
            "updated_at",
            "role",
        ]
        read_only_fields = ["id", "slug", "is_active", "created_at", "updated_at", "role"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_role(self, obj) -> str | None:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None
        membership = Membership.objects.filter(
            user=request.user,
            organization=obj,
            status=Membership.Status.ACTIVE,
        ).first()
        return membership.role if membership else None

    def validate_currency(self, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code.")
        return cleaned


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    category = serializers.ChoiceField(choices=Organization.Category.choices, default=Organization.Category.TAILOR)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    currency = serializers.CharField(max_length=3, required=False, default="NGN")
    preferred_unit = serializers.ChoiceField(
        choices=Organization.UnitSystem.choices,
        required=False,
        default=Organization.UnitSystem.CM,
    )

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Workspace name must be at least 2 characters.")
        return cleaned

    def validate_currency(self, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code.")
        return cleaned

    def create(self, validated_data):
        user = self.context["request"].user
        org, _ = create_organization_with_owner(user=user, **validated_data)
        return org


class MembershipSummarySerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "role", "status", "organization", "created_at"]
        read_only_fields = fields


class MembershipMemberSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "user_id", "email", "full_name", "role", "status", "created_at"]
        read_only_fields = fields


class MembershipUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Membership.Role.choices, required=False)
    status = serializers.ChoiceField(
        choices=[Membership.Status.ACTIVE, Membership.Status.SUSPENDED],
        required=False,
    )


class OrganizationInvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.CharField(source="invited_by.full_name", read_only=True, default=None)

    class Meta:
        model = OrganizationInvitation
        fields = [
            "id",
            "organization",
            "email",
            "role",
            "status",
            "expires_at",
            "invited_by",
            "invited_by_name",
            "accepted_at",
            "created_at",
        ]
        read_only_fields = fields


class OrganizationInvitationCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            Membership.Role.MANAGER,
            Membership.Role.ARTISAN,
            Membership.Role.SALES_ASSISTANT,
        ],
        default=Membership.Role.ARTISAN,
    )
    expires_in_days = serializers.IntegerField(min_value=1, max_value=30, default=7)


class OrganizationInvitationCreatedSerializer(OrganizationInvitationSerializer):
    token = serializers.CharField(read_only=True)
    invite_path = serializers.CharField(read_only=True)

    class Meta(OrganizationInvitationSerializer.Meta):
        fields = OrganizationInvitationSerializer.Meta.fields + ["token", "invite_path"]


class PublicInvitationDetailSerializer(serializers.Serializer):
    organization_name = serializers.CharField()
    organization_category = serializers.CharField()
    email = serializers.EmailField()
    role = serializers.CharField()
    expires_at = serializers.DateTimeField()
    invited_by_name = serializers.CharField(allow_null=True)
    account_exists = serializers.BooleanField()


class PublicInvitationAcceptSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")

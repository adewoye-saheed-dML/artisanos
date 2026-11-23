from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from locations.models import NigerianLGA, NigerianState, NigerianWard, PollingUnit

from .models import (
    ArtisanVerification,
    Membership,
    Organization,
    OrganizationInvitation,
    VerificationDocument,
)
from .services import (
    clean_skills_list,
    create_organization_with_owner,
    resolve_nigerian_location_hierarchy,
)


class OrganizationSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    category_label = serializers.CharField(source="get_category_display", read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True, default=None)
    lga_name = serializers.CharField(source="lga.name", read_only=True, default=None)
    ward_name = serializers.CharField(source="ward.name", read_only=True, default=None)
    polling_unit_name = serializers.CharField(source="polling_unit.name", read_only=True, default=None)
    polling_unit_code = serializers.CharField(source="polling_unit.pu_code", read_only=True, default=None)
    service_ward_names = serializers.SerializerMethodField()

    class Meta:
        model = Organization
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "category_label",
            "email",
            "phone",
            "address",
            "city",
            "country",
            "state",
            "state_name",
            "lga",
            "lga_name",
            "ward",
            "ward_name",
            "polling_unit",
            "polling_unit_name",
            "polling_unit_code",
            "service_wards",
            "service_ward_names",
            "landmark",
            "availability_status",
            "available_for_callout",
            "offers_goods",
            "offers_services",
            "callout_fee",
            "years_experience",
            "skills",
            "is_verified",
            "verification_status",
            "currency",
            "preferred_unit",
            "is_active",
            "created_at",
            "updated_at",
            "role",
        ]
        read_only_fields = [
            "id",
            "slug",
            "category_label",
            "state_name",
            "lga_name",
            "ward_name",
            "polling_unit_name",
            "polling_unit_code",
            "service_ward_names",
            "is_verified",
            "verification_status",
            "is_active",
            "created_at",
            "updated_at",
            "role",
        ]

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

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_service_ward_names(self, obj) -> list[str]:
        return [w.name for w in obj.service_wards.all()]

    def validate_currency(self, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code.")
        return cleaned

    def validate_skills(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Skills must be a list of short skill labels.")
        return clean_skills_list(value)

    def validate(self, attrs):
        location_keys = {"state", "lga", "ward", "polling_unit"}
        if any(k in attrs for k in location_keys):
            state = attrs.get("state", self.instance.state if self.instance else None)
            lga = attrs.get("lga", self.instance.lga if self.instance else None)
            ward = attrs.get("ward", self.instance.ward if self.instance else None)
            polling_unit = attrs.get("polling_unit", self.instance.polling_unit if self.instance else None)
            # If a parent changed and child wasn't explicitly passed, clear stale child
            if "state" in attrs and "lga" not in attrs and lga and (not state or lga.state_id != state.id):
                lga = None
                ward = None
                polling_unit = None
            if "lga" in attrs and "ward" not in attrs and ward and (not lga or ward.lga_id != lga.id):
                ward = None
                polling_unit = None
            if "ward" in attrs and "polling_unit" not in attrs and polling_unit and (not ward or polling_unit.ward_id != ward.id):
                polling_unit = None

            resolved_state, resolved_lga, resolved_ward, resolved_pu = resolve_nigerian_location_hierarchy(
                state=state,
                lga=lga,
                ward=ward,
                polling_unit=polling_unit,
            )
            attrs["state"] = resolved_state
            attrs["lga"] = resolved_lga
            attrs["ward"] = resolved_ward
            attrs["polling_unit"] = resolved_pu
            if resolved_lga and not attrs.get("city") and not (self.instance and self.instance.city):
                attrs["city"] = resolved_lga.name
            if resolved_state and not attrs.get("country"):
                attrs["country"] = "Nigeria"
        return attrs


class OrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    category = serializers.ChoiceField(choices=Organization.Category.choices, default=Organization.Category.TAILOR)
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Nigeria")
    state = serializers.PrimaryKeyRelatedField(
        queryset=NigerianState.objects.all(), required=False, allow_null=True
    )
    lga = serializers.PrimaryKeyRelatedField(
        queryset=NigerianLGA.objects.all(), required=False, allow_null=True
    )
    ward = serializers.PrimaryKeyRelatedField(
        queryset=NigerianWard.objects.all(), required=False, allow_null=True
    )
    polling_unit = serializers.PrimaryKeyRelatedField(
        queryset=PollingUnit.objects.all(), required=False, allow_null=True
    )
    service_wards = serializers.PrimaryKeyRelatedField(
        queryset=NigerianWard.objects.all(), many=True, required=False
    )
    landmark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    availability_status = serializers.ChoiceField(
        choices=Organization.AvailabilityStatus.choices,
        required=False,
        default=Organization.AvailabilityStatus.AVAILABLE,
    )
    available_for_callout = serializers.BooleanField(required=False, default=True)
    offers_goods = serializers.BooleanField(required=False, default=True)
    offers_services = serializers.BooleanField(required=False, default=True)
    callout_fee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
    years_experience = serializers.IntegerField(min_value=0, max_value=80, required=False, allow_null=True)
    skills = serializers.ListField(
        child=serializers.CharField(max_length=60),
        required=False,
        default=list,
    )
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


class VerificationDocumentSerializer(serializers.ModelSerializer):
    document_type_label = serializers.CharField(source="get_document_type_display", read_only=True)
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default=None)
    content_path = serializers.SerializerMethodField()

    class Meta:
        model = VerificationDocument
        fields = [
            "id",
            "document_type",
            "document_type_label",
            "original_filename",
            "content_type",
            "file_size_bytes",
            "uploaded_by_name",
            "content_path",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_content_path(self, obj) -> str:
        return f"/api/v1/organizations/{obj.organization_id}/verification/documents/{obj.id}/content/"


class VerificationDocumentUploadSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=VerificationDocument.DocumentType.choices)
    file = serializers.FileField()


class ArtisanVerificationSerializer(serializers.ModelSerializer):
    organization_id = serializers.UUIDField(source="organization.id", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    organization_category = serializers.CharField(source="organization.get_category_display", read_only=True)
    ward_name = serializers.CharField(source="organization.ward.name", read_only=True, default=None)
    polling_unit_name = serializers.CharField(source="organization.polling_unit.name", read_only=True, default=None)
    state_name = serializers.CharField(source="organization.state.name", read_only=True, default=None)
    nin_masked = serializers.SerializerMethodField()
    government_id_type_label = serializers.CharField(source="get_government_id_type_display", read_only=True)
    submitted_by_email = serializers.CharField(source="submitted_by.email", read_only=True, default=None)
    reviewed_by_email = serializers.CharField(source="reviewed_by.email", read_only=True, default=None)
    documents = VerificationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = ArtisanVerification
        fields = [
            "id",
            "organization_id",
            "organization_name",
            "organization_slug",
            "organization_category",
            "state_name",
            "ward_name",
            "polling_unit_name",
            "nin_masked",
            "nin_last4",
            "government_id_type",
            "government_id_type_label",
            "cac_number",
            "cac_business_name",
            "guarantor_name",
            "guarantor_phone",
            "bank_name",
            "bank_account_number",
            "bank_account_name",
            "status",
            "submitted_by_email",
            "submitted_at",
            "reviewed_by_email",
            "reviewed_at",
            "rejection_reason",
            "review_notes",
            "documents",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_nin_masked(self, obj) -> str:
        return f"*******{obj.nin_last4}" if obj.nin_last4 else ""


class ArtisanVerificationSubmitSerializer(serializers.Serializer):
    nin = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    government_id_type = serializers.ChoiceField(
        choices=ArtisanVerification.GovernmentIdType.choices,
        required=False,
        default=ArtisanVerification.GovernmentIdType.NIN_SLIP,
    )
    cac_number = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    cac_business_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    guarantor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    guarantor_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    bank_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    bank_account_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    bank_account_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

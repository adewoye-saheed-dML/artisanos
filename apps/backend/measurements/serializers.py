import json

from rest_framework import serializers

from customers.models import Customer
from measurement_templates.models import MeasurementTemplateVersion
from measurement_templates.serializers import MeasurementFieldSerializer

from .models import (
    MeasurementProfile,
    MeasurementRequest,
    MeasurementShareLink,
    MeasurementValue,
    MediaAccessLog,
    MediaAsset,
)


class MeasurementValueInputSerializer(serializers.Serializer):
    field_key = serializers.SlugField(max_length=64)
    numeric_value = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, allow_null=True)
    text_value = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")


class MeasurementValueSerializer(serializers.ModelSerializer):
    field_key = serializers.CharField(source="field.key", read_only=True)
    field_label = serializers.CharField(source="field.label", read_only=True)
    unit_type = serializers.CharField(source="field.unit_type", read_only=True)
    display_order = serializers.IntegerField(source="field.display_order", read_only=True)

    class Meta:
        model = MeasurementValue
        fields = [
            "id",
            "field",
            "field_key",
            "field_label",
            "unit_type",
            "display_order",
            "numeric_value",
            "text_value",
            "unit",
        ]


class MeasurementProfileSerializer(serializers.ModelSerializer):
    values = MeasurementValueSerializer(many=True, read_only=True)
    template_name = serializers.CharField(source="template_version.template.name", read_only=True)
    template_category = serializers.CharField(source="template_version.template.category", read_only=True)
    template_version_number = serializers.IntegerField(source="template_version.version_number", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)
    verified_by_name = serializers.CharField(source="verified_by.full_name", read_only=True, default=None)

    class Meta:
        model = MeasurementProfile
        fields = [
            "id",
            "organization",
            "customer",
            "template_version",
            "template_name",
            "template_category",
            "template_version_number",
            "label",
            "unit_system",
            "source",
            "status",
            "version_number",
            "parent_profile",
            "is_latest",
            "measured_at",
            "notes",
            "created_by",
            "created_by_name",
            "verified_by",
            "verified_by_name",
            "verified_at",
            "created_at",
            "updated_at",
            "values",
        ]
        read_only_fields = fields


class MeasurementProfileCreateSerializer(serializers.Serializer):
    template_version_id = serializers.UUIDField()
    label = serializers.CharField(max_length=120, required=False, default="Primary Measurements")
    unit_system = serializers.ChoiceField(
        choices=MeasurementProfile.UnitSystem.choices,
        default=MeasurementProfile.UnitSystem.CM,
    )
    status = serializers.ChoiceField(
        choices=[
            MeasurementProfile.Status.DRAFT,
            MeasurementProfile.Status.NEEDS_REVIEW,
            MeasurementProfile.Status.VERIFIED,
        ],
        default=MeasurementProfile.Status.VERIFIED,
    )
    measured_at = serializers.DateTimeField(required=False, allow_null=True)
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    values = MeasurementValueInputSerializer(many=True, min_length=1)

    def validate_template_version_id(self, value):
        try:
            return MeasurementTemplateVersion.objects.select_related("template").prefetch_related("fields").get(id=value)
        except MeasurementTemplateVersion.DoesNotExist as exc:
            raise serializers.ValidationError("Template version not found.") from exc


class MeasurementProfileReviseSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=120, required=False)
    unit_system = serializers.ChoiceField(choices=MeasurementProfile.UnitSystem.choices, required=False)
    status = serializers.ChoiceField(
        choices=[
            MeasurementProfile.Status.DRAFT,
            MeasurementProfile.Status.NEEDS_REVIEW,
            MeasurementProfile.Status.VERIFIED,
        ],
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True)
    values = MeasurementValueInputSerializer(many=True, required=False)


class MeasurementRequestSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    template_name = serializers.CharField(source="template_version.template.name", read_only=True)

    class Meta:
        model = MeasurementRequest
        fields = [
            "id",
            "customer",
            "customer_name",
            "template_version",
            "template_name",
            "status",
            "expires_at",
            "submitted_profile",
            "notes",
            "created_at",
        ]
        read_only_fields = fields


class MeasurementRequestCreateSerializer(serializers.Serializer):
    customer_id = serializers.UUIDField()
    template_version_id = serializers.UUIDField()
    expires_in_hours = serializers.IntegerField(min_value=1, max_value=720, default=72)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_customer_id(self, value):
        org = self.context["organization"]
        try:
            return Customer.objects.get(id=value, organization=org)
        except Customer.DoesNotExist as exc:
            raise serializers.ValidationError("Customer not found in this organization.") from exc

    def validate_template_version_id(self, value):
        try:
            return MeasurementTemplateVersion.objects.select_related("template").get(id=value)
        except MeasurementTemplateVersion.DoesNotExist as exc:
            raise serializers.ValidationError("Template version not found.") from exc


class PublicMeasurementRequestDetailSerializer(serializers.Serializer):
    organization_name = serializers.CharField()
    customer_first_name = serializers.CharField()
    preferred_unit = serializers.CharField()
    template_name = serializers.CharField()
    expires_at = serializers.DateTimeField()
    notes = serializers.CharField()
    fields = MeasurementFieldSerializer(many=True)


class PublicMeasurementSubmissionSerializer(serializers.Serializer):
    unit_system = serializers.ChoiceField(
        choices=MeasurementProfile.UnitSystem.choices,
        default=MeasurementProfile.UnitSystem.CM,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    consent_granted = serializers.BooleanField()
    values = MeasurementValueInputSerializer(many=True, min_length=1)


class MeasurementShareLinkSerializer(serializers.ModelSerializer):
    profile_label = serializers.CharField(source="profile.label", read_only=True)
    profile_version = serializers.IntegerField(source="profile.version_number", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)

    class Meta:
        model = MeasurementShareLink
        fields = [
            "id",
            "customer",
            "customer_name",
            "profile",
            "profile_label",
            "profile_version",
            "recipient_label",
            "status",
            "expires_at",
            "access_count",
            "last_accessed_at",
            "created_at",
        ]
        read_only_fields = fields


class MeasurementShareCreateSerializer(serializers.Serializer):
    profile_id = serializers.UUIDField()
    recipient_label = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    expires_in_days = serializers.IntegerField(min_value=1, max_value=90, default=14)
    consent_confirmed = serializers.BooleanField()

    def validate_profile_id(self, value):
        org = self.context["organization"]
        try:
            return MeasurementProfile.objects.select_related("customer").get(id=value, organization=org)
        except MeasurementProfile.DoesNotExist as exc:
            raise serializers.ValidationError("Measurement profile not found in this organization.") from exc


class MeasurementShareCreatedSerializer(MeasurementShareLinkSerializer):
    token = serializers.CharField(read_only=True)
    public_path = serializers.CharField(read_only=True)

    class Meta(MeasurementShareLinkSerializer.Meta):
        fields = MeasurementShareLinkSerializer.Meta.fields + ["token", "public_path"]


class PublicFitPassportSerializer(serializers.Serializer):
    issuing_organization = serializers.CharField()
    customer_first_name = serializers.CharField()
    profile_label = serializers.CharField()
    template_name = serializers.CharField()
    template_category = serializers.CharField()
    unit_system = serializers.CharField()
    version_number = serializers.IntegerField()
    verified_at = serializers.DateTimeField(allow_null=True)
    measured_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    values = MeasurementValueSerializer(many=True)


class ImportFromShareSerializer(serializers.Serializer):
    token = serializers.CharField(max_length=512)


class MediaAccessLogSerializer(serializers.ModelSerializer):
    accessed_by_name = serializers.CharField(source="accessed_by.full_name", read_only=True, default=None)

    class Meta:
        model = MediaAccessLog
        fields = ["id", "action", "accessed_by", "accessed_by_name", "ip_address", "notes", "created_at"]
        read_only_fields = fields


class MediaAssetSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True, default=None)
    consent_granted_at = serializers.DateTimeField(source="consent_record.granted_at", read_only=True)
    content_path = serializers.SerializerMethodField()

    class Meta:
        model = MediaAsset
        fields = [
            "id",
            "customer",
            "profile",
            "measurement_request",
            "view_angle",
            "content_type",
            "file_size_bytes",
            "quality_metadata",
            "allow_model_training",
            "consent_granted_at",
            "retention_expires_at",
            "status",
            "deleted_at",
            "uploaded_by",
            "uploaded_by_name",
            "content_path",
            "created_at",
        ]
        read_only_fields = fields

    def get_content_path(self, obj) -> str | None:
        if obj.status != MediaAsset.Status.ACTIVE:
            return None
        return f"/api/v1/customers/{obj.customer_id}/media/{obj.id}/content/"


class MediaAssetUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    view_angle = serializers.ChoiceField(choices=MediaAsset.ViewAngle.choices, default=MediaAsset.ViewAngle.FRONT)
    photo_consent_granted = serializers.BooleanField()
    allow_model_training = serializers.BooleanField(required=False, default=False)
    profile_id = serializers.UUIDField(required=False, allow_null=True)
    quality_metadata = serializers.CharField(required=False, allow_blank=True, default="{}")

    def validate_quality_metadata(self, value: str) -> dict:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise serializers.ValidationError("quality_metadata must be valid JSON.") from exc
        if not isinstance(parsed, dict):
            raise serializers.ValidationError("quality_metadata must be a JSON object.")
        return parsed

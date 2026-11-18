from django.db import transaction
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import MeasurementField, MeasurementTemplate, MeasurementTemplateVersion


class MeasurementFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = MeasurementField
        fields = [
            "id",
            "key",
            "label",
            "description",
            "unit_type",
            "default_unit",
            "min_value",
            "max_value",
            "is_required",
            "display_order",
            "guidance_text",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        min_v = attrs.get("min_value")
        max_v = attrs.get("max_value")
        if min_v is not None and max_v is not None and min_v > max_v:
            raise serializers.ValidationError("min_value cannot exceed max_value.")
        return attrs


class MeasurementTemplateVersionSerializer(serializers.ModelSerializer):
    fields = MeasurementFieldSerializer(many=True, read_only=True)

    class Meta:
        model = MeasurementTemplateVersion
        fields = ["id", "version_number", "is_published", "changelog", "created_at", "fields"]
        read_only_fields = fields


class MeasurementTemplateSerializer(serializers.ModelSerializer):
    is_system = serializers.BooleanField(read_only=True)
    latest_version = serializers.SerializerMethodField()

    class Meta:
        model = MeasurementTemplate
        fields = [
            "id",
            "organization",
            "is_system",
            "name",
            "slug",
            "category",
            "description",
            "is_active",
            "created_at",
            "updated_at",
            "latest_version",
        ]
        read_only_fields = ["id", "organization", "is_system", "slug", "created_at", "updated_at", "latest_version"]

    @extend_schema_field(MeasurementTemplateVersionSerializer(allow_null=True))
    def get_latest_version(self, obj):
        version = obj.versions.filter(is_published=True).order_by("-version_number").first()
        if not version:
            return None
        return MeasurementTemplateVersionSerializer(version).data


class MeasurementTemplateCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    category = serializers.ChoiceField(choices=MeasurementTemplate.Category.choices)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    changelog = serializers.CharField(max_length=255, required=False, allow_blank=True, default="Initial version")
    fields = MeasurementFieldSerializer(many=True, min_length=1)

    def validate_fields(self, fields):
        seen_keys = set()
        for f in fields:
            key = f["key"]
            if key in seen_keys:
                raise serializers.ValidationError(f"Duplicate field key '{key}'.")
            seen_keys.add(key)
        return fields

    @transaction.atomic
    def create(self, validated_data):
        org = self.context["organization"]
        user = self.context["request"].user
        fields_data = validated_data.pop("fields")
        changelog = validated_data.pop("changelog", "Initial version")

        base_slug = slugify(validated_data["name"])[:140] or "custom-template"
        slug = base_slug
        counter = 1
        while MeasurementTemplate.objects.filter(organization=org, slug=slug).exists():
            counter += 1
            slug = f"{base_slug}-{counter}"

        template = MeasurementTemplate.objects.create(
            organization=org,
            name=validated_data["name"].strip(),
            slug=slug,
            category=validated_data["category"],
            description=validated_data.get("description", "").strip(),
        )
        version = MeasurementTemplateVersion.objects.create(
            template=template,
            version_number=1,
            is_published=True,
            changelog=changelog,
            created_by=user,
        )
        for idx, field_data in enumerate(fields_data, start=1):
            field_data = dict(field_data)
            field_data.setdefault("display_order", idx)
            MeasurementField.objects.create(template_version=version, **field_data)
        return template


class MeasurementTemplateVersionCreateSerializer(serializers.Serializer):
    changelog = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    fields = MeasurementFieldSerializer(many=True, min_length=1)

    def validate_fields(self, fields):
        seen_keys = set()
        for f in fields:
            if f["key"] in seen_keys:
                raise serializers.ValidationError(f"Duplicate field key '{f['key']}'.")
            seen_keys.add(f["key"])
        return fields

    @transaction.atomic
    def create(self, validated_data):
        template = self.context["template"]
        user = self.context["request"].user
        latest = template.versions.order_by("-version_number").first()
        next_num = (latest.version_number + 1) if latest else 1
        version = MeasurementTemplateVersion.objects.create(
            template=template,
            version_number=next_num,
            is_published=True,
            changelog=validated_data.get("changelog", f"Version {next_num}"),
            created_by=user,
        )
        for idx, field_data in enumerate(validated_data["fields"], start=1):
            field_data = dict(field_data)
            field_data.setdefault("display_order", idx)
            MeasurementField.objects.create(template_version=version, **field_data)
        return version

from django.contrib import admin

from .models import (
    MeasurementProfile,
    MeasurementRequest,
    MeasurementShareLink,
    MeasurementValue,
    MediaAccessLog,
    MediaAsset,
)


@admin.register(MeasurementProfile)
class MeasurementProfileAdmin(admin.ModelAdmin):
    list_display = ["customer", "template_version", "version_number", "unit_system", "status", "is_latest", "measured_at"]
    list_filter = ["status", "unit_system", "source", "is_latest"]


@admin.register(MeasurementValue)
class MeasurementValueAdmin(admin.ModelAdmin):
    list_display = ["profile", "field", "numeric_value", "text_value", "unit"]


@admin.register(MeasurementRequest)
class MeasurementRequestAdmin(admin.ModelAdmin):
    list_display = ["customer", "organization", "status", "expires_at", "created_at"]
    list_filter = ["status"]


@admin.register(MeasurementShareLink)
class MeasurementShareLinkAdmin(admin.ModelAdmin):
    list_display = ["customer", "profile", "status", "access_count", "expires_at", "created_at"]
    list_filter = ["status"]


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ["customer", "view_angle", "status", "file_size_bytes", "retention_expires_at", "created_at"]
    list_filter = ["status", "view_angle", "allow_model_training"]


@admin.register(MediaAccessLog)
class MediaAccessLogAdmin(admin.ModelAdmin):
    list_display = ["asset", "action", "accessed_by", "ip_address", "created_at"]
    list_filter = ["action"]

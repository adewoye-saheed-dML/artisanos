from django.contrib import admin

from .models import MeasurementField, MeasurementTemplate, MeasurementTemplateVersion


@admin.register(MeasurementTemplate)
class MeasurementTemplateAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "category", "organization", "is_active"]
    list_filter = ["category", "is_active"]


@admin.register(MeasurementTemplateVersion)
class MeasurementTemplateVersionAdmin(admin.ModelAdmin):
    list_display = ["template", "version_number", "is_published", "created_at"]


@admin.register(MeasurementField)
class MeasurementFieldAdmin(admin.ModelAdmin):
    list_display = ["label", "key", "template_version", "unit_type", "default_unit", "is_required", "display_order"]

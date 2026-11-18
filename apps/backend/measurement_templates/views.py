from django.db import transaction
from django.db.models import Q
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenancy import TenantScopedMixin
from organizations.models import Membership

from .models import MeasurementField, MeasurementTemplate, MeasurementTemplateVersion
from .serializers import (
    MeasurementTemplateCreateSerializer,
    MeasurementTemplateSerializer,
    MeasurementTemplateVersionCreateSerializer,
    MeasurementTemplateVersionSerializer,
)


class MeasurementTemplateViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """List system + org measurement templates and create custom org templates."""

    serializer_class = MeasurementTemplateSerializer
    filterset_fields = ["category", "is_active"]
    search_fields = ["name", "description"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MeasurementTemplate.objects.none()
        org = self.get_organization()
        return (
            MeasurementTemplate.objects.filter(Q(organization__isnull=True) | Q(organization=org))
            .prefetch_related("versions__fields")
            .order_by("category", "name")
        )

    def _require_manager(self):
        membership = self.get_membership()
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only owners or managers can create or modify templates.")

    def create(self, request, *args, **kwargs):
        self._require_manager()
        serializer = MeasurementTemplateCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        template = serializer.save()
        return Response(
            MeasurementTemplateSerializer(template, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_update(self, serializer):
        self._require_manager()
        template = self.get_object()
        if template.is_system:
            raise exceptions.PermissionDenied("Built-in system templates cannot be modified.")
        serializer.save()

    @extend_schema(
        request=MeasurementTemplateVersionCreateSerializer,
        responses={201: MeasurementTemplateVersionSerializer},
    )
    @action(detail=True, methods=["post"])
    def versions(self, request, pk=None):
        self._require_manager()
        template = self.get_object()
        if template.is_system:
            raise exceptions.PermissionDenied("Cannot add custom versions directly to a system template.")
        context = self.get_serializer_context()
        context["template"] = template
        serializer = MeasurementTemplateVersionCreateSerializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        version = serializer.save()
        return Response(MeasurementTemplateVersionSerializer(version).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={201: MeasurementTemplateSerializer})
    @action(detail=True, methods=["post"])
    @transaction.atomic
    def clone(self, request, pk=None):
        """Clone any system or workspace template into a new customizable workspace template."""
        self._require_manager()
        org = self.get_organization()
        source = self.get_object()
        source_version = source.versions.filter(is_published=True).order_by("-version_number").first()
        if not source_version:
            raise exceptions.ValidationError("Source template has no published version to clone.")

        custom_name = (request.data.get("name") or f"{source.name} (Custom)").strip()[:150]
        base_slug = slugify(custom_name)[:140] or "custom-template"
        slug = base_slug
        counter = 1
        while MeasurementTemplate.objects.filter(organization=org, slug=slug).exists():
            counter += 1
            slug = f"{base_slug}-{counter}"

        cloned = MeasurementTemplate.objects.create(
            organization=org,
            name=custom_name,
            slug=slug,
            category=source.category,
            description=source.description,
        )
        new_version = MeasurementTemplateVersion.objects.create(
            template=cloned,
            version_number=1,
            is_published=True,
            changelog=f"Cloned from {source.name} v{source_version.version_number}",
            created_by=request.user,
        )
        MeasurementField.objects.bulk_create(
            [
                MeasurementField(
                    template_version=new_version,
                    key=f.key,
                    label=f.label,
                    description=f.description,
                    unit_type=f.unit_type,
                    default_unit=f.default_unit,
                    min_value=f.min_value,
                    max_value=f.max_value,
                    is_required=f.is_required,
                    display_order=f.display_order,
                    guidance_text=f.guidance_text,
                )
                for f in source_version.fields.order_by("display_order", "label")
            ]
        )
        return Response(
            MeasurementTemplateSerializer(cloned, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

import uuid

from rest_framework import exceptions
from rest_framework.permissions import BasePermission

from organizations.models import Membership


def resolve_organization_context(request):
    """
    Resolve and verify the active organization from X-Organization-Id against
    the authenticated user's active Membership records.
    """
    if hasattr(request, "_cached_membership") and request._cached_membership is not None:
        return request._cached_membership

    org_header = request.headers.get("X-Organization-Id")
    if not org_header:
        raise exceptions.PermissionDenied("X-Organization-Id header is required.")

    try:
        org_uuid = uuid.UUID(str(org_header))
    except ValueError as exc:
        raise exceptions.ValidationError({"organization": "Invalid X-Organization-Id UUID."}) from exc

    membership = (
        Membership.objects.select_related("organization")
        .filter(
            user=request.user,
            organization_id=org_uuid,
            status=Membership.Status.ACTIVE,
            organization__is_active=True,
        )
        .first()
    )
    if membership is None:
        raise exceptions.PermissionDenied("You do not have active membership in this organization.")

    request._cached_membership = membership
    request.membership = membership
    request.organization = membership.organization
    return membership


class ActiveOrganizationPermission(BasePermission):
    """Requires an authenticated user with active membership in X-Organization-Id."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        resolve_organization_context(request)
        return True


def require_organization_roles(*allowed_roles: str):
    """Build a DRF permission class requiring one of the specified organization roles."""

    class RolePermission(BasePermission):
        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False
            membership = resolve_organization_context(request)
            if membership.role not in allowed_roles:
                raise exceptions.PermissionDenied(
                    f"This action requires one of the following roles: {', '.join(allowed_roles)}."
                )
            return True

    return RolePermission


class TenantScopedMixin:
    """Mixin for DRF views/viewsets operating strictly inside request.organization."""

    permission_classes = [ActiveOrganizationPermission]

    def get_organization(self):
        return resolve_organization_context(self.request).organization

    def get_membership(self):
        return resolve_organization_context(self.request)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if getattr(self.request, "user", None) and self.request.user.is_authenticated:
            if self.request.headers.get("X-Organization-Id"):
                membership = resolve_organization_context(self.request)
                context["organization"] = membership.organization
                context["membership"] = membership
        return context

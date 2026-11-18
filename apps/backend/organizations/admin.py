from django.contrib import admin

from .models import Membership, Organization, OrganizationInvitation


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "category", "currency", "preferred_unit", "is_active", "created_at"]
    search_fields = ["name", "slug"]
    list_filter = ["category", "is_active"]


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ["user", "organization", "role", "status", "created_at"]
    list_filter = ["role", "status"]
    search_fields = ["user__email", "organization__name"]


@admin.register(OrganizationInvitation)
class OrganizationInvitationAdmin(admin.ModelAdmin):
    list_display = ["email", "organization", "role", "status", "expires_at", "created_at"]
    list_filter = ["role", "status"]
    search_fields = ["email", "organization__name"]

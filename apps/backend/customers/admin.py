from django.contrib import admin

from .models import ConsentRecord, Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["full_name", "phone", "email", "organization", "is_archived", "created_at"]
    list_filter = ["is_archived", "preferred_contact_method"]
    search_fields = ["full_name", "phone", "email"]


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ["customer", "consent_type", "granted", "granted_at", "created_at"]
    list_filter = ["consent_type", "granted"]

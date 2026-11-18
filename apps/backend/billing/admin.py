from django.contrib import admin

from .models import AuditLog, PaymentTransaction, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "monthly_price", "currency", "max_members", "max_customers", "is_active"]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["organization", "plan", "status", "provider", "current_period_end"]
    list_filter = ["status", "provider", "plan"]


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ["reference", "organization", "plan", "amount", "currency", "status", "verified_at"]
    list_filter = ["status", "provider"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "organization", "actor", "target_type", "created_at"]
    list_filter = ["action"]

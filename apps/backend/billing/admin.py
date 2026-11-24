from django.contrib import admin

from .models import AuditLog, MarketplaceBoost, PaymentTransaction, Plan, Subscription


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "code",
        "monthly_price",
        "annual_price",
        "escrow_fee_rate_pct",
        "monthly_free_boosts",
        "currency",
        "is_active",
    ]


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["organization", "plan", "billing_cycle", "status", "provider", "current_period_end"]
    list_filter = ["status", "billing_cycle", "provider", "plan"]


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = [
        "reference",
        "purpose",
        "organization",
        "plan",
        "amount",
        "currency",
        "status",
        "verified_at",
    ]
    list_filter = ["purpose", "status", "provider"]


@admin.register(MarketplaceBoost)
class MarketplaceBoostAdmin(admin.ModelAdmin):
    list_display = [
        "organization",
        "boost_type",
        "product",
        "status",
        "amount",
        "used_plan_credit",
        "starts_at",
        "ends_at",
    ]
    list_filter = ["boost_type", "status", "used_plan_credit"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["action", "organization", "actor", "target_type", "created_at"]
    list_filter = ["action"]

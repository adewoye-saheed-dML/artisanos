from django.contrib import admin

from .models import EscrowEvent, EscrowTransaction


@admin.register(EscrowTransaction)
class EscrowTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "organization",
        "customer_name",
        "total_amount",
        "held_in_escrow_amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "currency", "payment_provider")
    search_fields = ("reference", "job_title", "customer_name", "organization__name")


@admin.register(EscrowEvent)
class EscrowEventAdmin(admin.ModelAdmin):
    list_display = ("escrow", "event_type", "from_status", "to_status", "created_at")
    list_filter = ("event_type",)

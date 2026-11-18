from django.contrib import admin

from .models import Order, OrderStatusEvent


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "customer", "garment_type", "status", "quoted_amount", "currency", "created_at"]
    list_filter = ["status", "payment_status", "currency"]
    search_fields = ["order_number", "garment_type", "customer__full_name"]


@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(admin.ModelAdmin):
    list_display = ["order", "from_status", "to_status", "changed_by", "created_at"]

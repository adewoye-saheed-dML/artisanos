from django.contrib import admin

from .models import ProductionTask


@admin.register(ProductionTask)
class ProductionTaskAdmin(admin.ModelAdmin):
    list_display = ["title", "order", "stage", "status", "is_alteration", "assigned_to", "due_date"]
    list_filter = ["status", "stage", "is_alteration"]
    search_fields = ["title", "order__order_number"]

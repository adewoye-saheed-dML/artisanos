from django.contrib import admin

from .models import InventoryMovement, Product, ProductVariant, Storefront, StorefrontInquiry


@admin.register(Storefront)
class StorefrontAdmin(admin.ModelAdmin):
    list_display = ["organization", "headline", "is_published", "updated_at"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ["name", "organization", "product_type", "price", "currency", "stock_quantity", "status"]
    list_filter = ["status", "product_type"]
    search_fields = ["name", "sku"]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["product", "name", "stock_quantity", "is_active"]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ["product", "movement_type", "quantity_delta", "balance_after", "performed_by", "created_at"]
    list_filter = ["movement_type"]


@admin.register(StorefrontInquiry)
class StorefrontInquiryAdmin(admin.ModelAdmin):
    list_display = ["buyer_name", "buyer_phone", "product", "status", "created_at"]
    list_filter = ["status"]

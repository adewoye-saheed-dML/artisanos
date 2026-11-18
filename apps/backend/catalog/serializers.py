from decimal import Decimal

from rest_framework import serializers

from .models import InventoryMovement, Product, ProductVariant, Storefront, StorefrontInquiry


class ProductVariantSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "product",
            "name",
            "sku",
            "price_override",
            "stock_quantity",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "product", "created_at"]


class InventoryMovementSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source="performed_by.full_name", read_only=True, default=None)
    variant_name = serializers.CharField(source="variant.name", read_only=True, default=None)

    class Meta:
        model = InventoryMovement
        fields = [
            "id",
            "product",
            "variant",
            "variant_name",
            "movement_type",
            "quantity_delta",
            "balance_after",
            "reason",
            "performed_by",
            "performed_by_name",
            "created_at",
        ]
        read_only_fields = fields


class InventoryAdjustmentInputSerializer(serializers.Serializer):
    movement_type = serializers.ChoiceField(
        choices=[
            InventoryMovement.MovementType.RESTOCK,
            InventoryMovement.MovementType.SALE,
            InventoryMovement.MovementType.ADJUSTMENT,
            InventoryMovement.MovementType.RETURN,
            InventoryMovement.MovementType.DAMAGE,
        ]
    )
    quantity_delta = serializers.IntegerField()
    reason = serializers.CharField(max_length=255)
    variant = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_reason(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Provide a short reason for this stock adjustment.")
        return cleaned


class ProductSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "organization",
            "name",
            "slug",
            "description",
            "category",
            "product_type",
            "price",
            "currency",
            "image_url",
            "sku",
            "status",
            "track_inventory",
            "stock_quantity",
            "variants",
            "created_at",
            "updated_at",
        ]
        # stock_quantity is strictly read-only on updates; use /adjust-inventory/
        read_only_fields = [
            "id",
            "organization",
            "slug",
            "stock_quantity",
            "variants",
            "created_at",
            "updated_at",
        ]


class ProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=160)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    category = serializers.CharField(max_length=64, required=False, default="Bespoke Tailoring")
    product_type = serializers.ChoiceField(
        choices=Product.ProductType.choices,
        default=Product.ProductType.MADE_TO_ORDER,
    )
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.00"))
    currency = serializers.CharField(max_length=3, required=False)
    image_url = serializers.CharField(max_length=500, required=False, allow_blank=True, default="")
    sku = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=Product.Status.choices, default=Product.Status.DRAFT)
    track_inventory = serializers.BooleanField(required=False)
    initial_stock = serializers.IntegerField(min_value=0, required=False, default=0)

    def validate_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Product name must be at least 2 characters.")
        return cleaned


class StorefrontSettingsSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    slug = serializers.CharField(source="organization.slug", read_only=True)
    category = serializers.CharField(source="organization.category", read_only=True)
    city = serializers.CharField(source="organization.city", read_only=True)
    country = serializers.CharField(source="organization.country", read_only=True)
    currency = serializers.CharField(source="organization.currency", read_only=True)

    class Meta:
        model = Storefront
        fields = [
            "id",
            "organization_name",
            "slug",
            "category",
            "city",
            "country",
            "currency",
            "headline",
            "bio",
            "whatsapp_number",
            "instagram_handle",
            "is_published",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization_name",
            "slug",
            "category",
            "city",
            "country",
            "currency",
            "updated_at",
        ]


class StorefrontInquirySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)

    class Meta:
        model = StorefrontInquiry
        fields = [
            "id",
            "product",
            "product_name",
            "buyer_name",
            "buyer_phone",
            "buyer_email",
            "message",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product",
            "product_name",
            "buyer_name",
            "buyer_phone",
            "buyer_email",
            "message",
            "created_at",
        ]


class PublicStorefrontInquiryCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    buyer_name = serializers.CharField(max_length=150)
    buyer_phone = serializers.CharField(max_length=32)
    buyer_email = serializers.EmailField(required=False, allow_blank=True, default="")
    message = serializers.CharField()

    def validate_buyer_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Please enter your name.")
        return cleaned

    def validate_buyer_phone(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Please provide a valid phone or WhatsApp number.")
        return cleaned

    def validate_message(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Please include a short message about your inquiry.")
        return cleaned


class PublicStorefrontResponseSerializer(serializers.Serializer):
    storefront = StorefrontSettingsSerializer()
    products = ProductSerializer(many=True)


class MarketplaceStorefrontCardSerializer(serializers.Serializer):
    organization_name = serializers.CharField()
    slug = serializers.CharField()
    category = serializers.CharField()
    city = serializers.CharField()
    country = serializers.CharField()
    headline = serializers.CharField()
    bio = serializers.CharField()
    published_product_count = serializers.IntegerField()


class MarketplaceProductCardSerializer(ProductSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    storefront_slug = serializers.CharField(source="organization.slug", read_only=True)
    organization_city = serializers.CharField(source="organization.city", read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + [
            "organization_name",
            "storefront_slug",
            "organization_city",
        ]

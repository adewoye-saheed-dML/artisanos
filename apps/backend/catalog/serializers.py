from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from locations.models import NigerianWard, PollingUnit

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
    category_label = serializers.CharField(source="organization.get_category_display", read_only=True)
    phone = serializers.CharField(source="organization.phone", read_only=True)
    city = serializers.CharField(source="organization.city", read_only=True)
    country = serializers.CharField(source="organization.country", read_only=True)
    currency = serializers.CharField(source="organization.currency", read_only=True)
    state_id = serializers.UUIDField(source="organization.state_id", read_only=True, allow_null=True)
    state_name = serializers.CharField(source="organization.state.name", read_only=True, default=None)
    lga_id = serializers.UUIDField(source="organization.lga_id", read_only=True, allow_null=True)
    lga_name = serializers.CharField(source="organization.lga.name", read_only=True, default=None)
    ward_id = serializers.UUIDField(source="organization.ward_id", read_only=True, allow_null=True)
    ward_name = serializers.CharField(source="organization.ward.name", read_only=True, default=None)
    polling_unit_id = serializers.UUIDField(source="organization.polling_unit_id", read_only=True, allow_null=True)
    polling_unit_name = serializers.CharField(source="organization.polling_unit.name", read_only=True, default=None)
    polling_unit_code = serializers.CharField(source="organization.polling_unit.pu_code", read_only=True, default=None)
    landmark = serializers.CharField(source="organization.landmark", read_only=True)
    service_ward_names = serializers.SerializerMethodField()
    availability_status = serializers.CharField(source="organization.availability_status", read_only=True)
    available_for_callout = serializers.BooleanField(source="organization.available_for_callout", read_only=True)
    offers_goods = serializers.BooleanField(source="organization.offers_goods", read_only=True)
    offers_services = serializers.BooleanField(source="organization.offers_services", read_only=True)
    callout_fee = serializers.DecimalField(
        source="organization.callout_fee",
        max_digits=12,
        decimal_places=2,
        read_only=True,
        allow_null=True,
    )
    years_experience = serializers.IntegerField(
        source="organization.years_experience",
        read_only=True,
        allow_null=True,
    )
    skills = serializers.JSONField(source="organization.skills", read_only=True)
    is_verified = serializers.BooleanField(source="organization.is_verified", read_only=True)
    verification_status = serializers.CharField(
        source="organization.verification_status", read_only=True
    )
    cac_verified = serializers.SerializerMethodField()

    class Meta:
        model = Storefront
        fields = [
            "id",
            "organization_name",
            "slug",
            "category",
            "category_label",
            "phone",
            "city",
            "country",
            "currency",
            "state_id",
            "state_name",
            "lga_id",
            "lga_name",
            "ward_id",
            "ward_name",
            "polling_unit_id",
            "polling_unit_name",
            "polling_unit_code",
            "landmark",
            "service_ward_names",
            "availability_status",
            "available_for_callout",
            "offers_goods",
            "offers_services",
            "callout_fee",
            "years_experience",
            "skills",
            "is_verified",
            "verification_status",
            "cac_verified",
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
            "category_label",
            "phone",
            "city",
            "country",
            "currency",
            "state_id",
            "state_name",
            "lga_id",
            "lga_name",
            "ward_id",
            "ward_name",
            "polling_unit_id",
            "polling_unit_name",
            "polling_unit_code",
            "landmark",
            "service_ward_names",
            "availability_status",
            "available_for_callout",
            "offers_goods",
            "offers_services",
            "callout_fee",
            "years_experience",
            "skills",
            "is_verified",
            "verification_status",
            "cac_verified",
            "updated_at",
        ]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_service_ward_names(self, obj) -> list[str]:
        return [w.name for w in obj.organization.service_wards.all()]

    @extend_schema_field(serializers.BooleanField())
    def get_cac_verified(self, obj) -> bool:
        if not obj.organization.is_verified:
            return False
        kyc = getattr(obj.organization, "kyc_verification", None)
        return bool(kyc and kyc.cac_number)


class StorefrontInquirySerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    customer_ward_name = serializers.CharField(source="customer_ward.name", read_only=True, default=None)
    customer_polling_unit_name = serializers.CharField(
        source="customer_polling_unit.name", read_only=True, default=None
    )
    customer_polling_unit_code = serializers.CharField(
        source="customer_polling_unit.pu_code", read_only=True, default=None
    )
    converted_order_number = serializers.CharField(
        source="converted_order.order_number", read_only=True, default=None
    )

    class Meta:
        model = StorefrontInquiry
        fields = [
            "id",
            "product",
            "product_name",
            "inquiry_type",
            "urgency",
            "buyer_name",
            "buyer_phone",
            "buyer_email",
            "customer_ward",
            "customer_ward_name",
            "customer_polling_unit",
            "customer_polling_unit_name",
            "customer_polling_unit_code",
            "customer_address",
            "preferred_date",
            "quantity",
            "budget_amount",
            "message",
            "status",
            "converted_order",
            "converted_order_number",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product",
            "product_name",
            "inquiry_type",
            "urgency",
            "buyer_name",
            "buyer_phone",
            "buyer_email",
            "customer_ward",
            "customer_ward_name",
            "customer_polling_unit",
            "customer_polling_unit_name",
            "customer_polling_unit_code",
            "customer_address",
            "preferred_date",
            "quantity",
            "budget_amount",
            "message",
            "converted_order",
            "converted_order_number",
            "created_at",
        ]


class PublicStorefrontInquiryCreateSerializer(serializers.Serializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )
    inquiry_type = serializers.ChoiceField(
        choices=StorefrontInquiry.InquiryType.choices,
        required=False,
        allow_null=True,
    )
    urgency = serializers.ChoiceField(
        choices=StorefrontInquiry.Urgency.choices,
        required=False,
        default=StorefrontInquiry.Urgency.NORMAL,
    )
    buyer_name = serializers.CharField(max_length=150)
    buyer_phone = serializers.CharField(max_length=32)
    buyer_email = serializers.EmailField(required=False, allow_blank=True, default="")
    customer_ward = serializers.PrimaryKeyRelatedField(
        queryset=NigerianWard.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_polling_unit = serializers.PrimaryKeyRelatedField(
        queryset=PollingUnit.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    preferred_date = serializers.DateField(required=False, allow_null=True)
    quantity = serializers.IntegerField(min_value=1, max_value=999, required=False, default=1)
    budget_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
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
            raise serializers.ValidationError("Please include a short message about your job or order.")
        return cleaned


class PublicStorefrontResponseSerializer(serializers.Serializer):
    storefront = StorefrontSettingsSerializer()
    products = ProductSerializer(many=True)


class MarketplaceStorefrontCardSerializer(serializers.Serializer):
    organization_name = serializers.CharField()
    slug = serializers.CharField()
    category = serializers.CharField()
    category_label = serializers.CharField()
    phone = serializers.CharField()
    whatsapp_number = serializers.CharField()
    instagram_handle = serializers.CharField()
    city = serializers.CharField()
    country = serializers.CharField()
    state_id = serializers.UUIDField(allow_null=True)
    state_name = serializers.CharField(allow_null=True)
    lga_id = serializers.UUIDField(allow_null=True)
    lga_name = serializers.CharField(allow_null=True)
    ward_id = serializers.UUIDField(allow_null=True)
    ward_name = serializers.CharField(allow_null=True)
    polling_unit_id = serializers.UUIDField(allow_null=True)
    polling_unit_name = serializers.CharField(allow_null=True)
    polling_unit_code = serializers.CharField(allow_null=True)
    landmark = serializers.CharField()
    service_ward_names = serializers.ListField(child=serializers.CharField())
    headline = serializers.CharField()
    bio = serializers.CharField()
    skills = serializers.ListField(child=serializers.CharField())
    availability_status = serializers.CharField()
    available_for_callout = serializers.BooleanField()
    offers_goods = serializers.BooleanField()
    offers_services = serializers.BooleanField()
    callout_fee = serializers.DecimalField(max_digits=12, decimal_places=2, allow_null=True)
    currency = serializers.CharField()
    years_experience = serializers.IntegerField(allow_null=True)
    is_verified = serializers.BooleanField()
    verification_status = serializers.CharField()
    cac_verified = serializers.BooleanField()
    published_product_count = serializers.IntegerField()
    published_service_count = serializers.IntegerField()
    is_featured = serializers.BooleanField(default=False)
    boost_badge = serializers.CharField(allow_blank=True, default="")
    proximity_tier = serializers.CharField(allow_null=True)
    proximity_label = serializers.CharField(allow_null=True)
    distance_km = serializers.FloatField(allow_null=True)


class MarketplaceProductCardSerializer(ProductSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    storefront_slug = serializers.CharField(source="organization.slug", read_only=True)
    organization_category = serializers.CharField(source="organization.category", read_only=True)
    organization_category_label = serializers.CharField(
        source="organization.get_category_display", read_only=True
    )
    organization_city = serializers.CharField(source="organization.city", read_only=True)
    organization_phone = serializers.CharField(source="organization.phone", read_only=True)
    whatsapp_number = serializers.SerializerMethodField()
    state_name = serializers.CharField(source="organization.state.name", read_only=True, default=None)
    lga_name = serializers.CharField(source="organization.lga.name", read_only=True, default=None)
    ward_name = serializers.CharField(source="organization.ward.name", read_only=True, default=None)
    polling_unit_name = serializers.CharField(
        source="organization.polling_unit.name", read_only=True, default=None
    )
    is_featured = serializers.SerializerMethodField()
    boost_badge = serializers.SerializerMethodField()
    proximity_tier = serializers.SerializerMethodField()
    proximity_label = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + [
            "organization_name",
            "storefront_slug",
            "organization_category",
            "organization_category_label",
            "organization_city",
            "organization_phone",
            "whatsapp_number",
            "state_name",
            "lga_name",
            "ward_name",
            "polling_unit_name",
            "is_featured",
            "boost_badge",
            "proximity_tier",
            "proximity_label",
            "distance_km",
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_is_featured(self, obj) -> bool:
        return bool(getattr(obj, "_is_featured", False))

    @extend_schema_field(serializers.CharField())
    def get_boost_badge(self, obj) -> str:
        return str(getattr(obj, "_boost_badge", "") or "")

    @extend_schema_field(serializers.CharField())
    def get_whatsapp_number(self, obj) -> str:
        sf = getattr(obj.organization, "storefront", None)
        return (sf.whatsapp_number if sf else "") or obj.organization.phone or ""

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_proximity_tier(self, obj) -> str | None:
        return getattr(obj, "_proximity_tier", None)

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_proximity_label(self, obj) -> str | None:
        return getattr(obj, "_proximity_label", None)

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_distance_km(self, obj) -> float | None:
        return getattr(obj, "_distance_km", None)


class MarketplaceCategoryCountSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()
    artisan_count = serializers.IntegerField()

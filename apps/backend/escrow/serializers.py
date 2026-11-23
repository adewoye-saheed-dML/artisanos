from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.models import StorefrontInquiry
from orders.models import Order
from organizations.models import Organization

from .models import EscrowEvent, EscrowTransaction
from .services import MAX_MATERIALS_ADVANCE_PCT


class EscrowEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.full_name", read_only=True, default=None)

    class Meta:
        model = EscrowEvent
        fields = [
            "id",
            "event_type",
            "from_status",
            "to_status",
            "notes",
            "actor",
            "actor_name",
            "created_at",
        ]
        read_only_fields = fields


class EscrowTransactionSerializer(serializers.ModelSerializer):
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    organization_slug = serializers.CharField(source="organization.slug", read_only=True)
    organization_category_label = serializers.CharField(
        source="organization.get_category_display", read_only=True
    )
    organization_phone = serializers.CharField(source="organization.phone", read_only=True)
    organization_is_verified = serializers.BooleanField(source="organization.is_verified", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True, default=None)
    events = EscrowEventSerializer(many=True, read_only=True)
    viewer_role = serializers.SerializerMethodField()

    class Meta:
        model = EscrowTransaction
        fields = [
            "id",
            "reference",
            "organization",
            "organization_name",
            "organization_slug",
            "organization_category_label",
            "organization_phone",
            "organization_is_verified",
            "customer_user",
            "customer_name",
            "customer_phone",
            "customer_email",
            "order",
            "order_number",
            "inquiry",
            "job_title",
            "job_description",
            "total_amount",
            "materials_advance_pct",
            "materials_advance_amount",
            "held_in_escrow_amount",
            "platform_fee_amount",
            "artisan_payout_amount",
            "currency",
            "status",
            "payment_provider",
            "artisan_completion_notes",
            "dispute_reason",
            "resolution_notes",
            "funded_at",
            "work_submitted_at",
            "released_at",
            "disputed_at",
            "resolved_at",
            "created_at",
            "updated_at",
            "viewer_role",
            "events",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_viewer_role(self, obj) -> str:
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return "guest"
        if obj.customer_user_id == request.user.id:
            return "customer"
        if request.user.is_platform_admin:
            return "admin"
        return "artisan"


class EscrowCreateSerializer(serializers.Serializer):
    organization_slug = serializers.SlugField(required=False, allow_blank=True, default="")
    organization_id = serializers.UUIDField(required=False, allow_null=True)
    job_title = serializers.CharField(max_length=180)
    job_description = serializers.CharField(required=False, allow_blank=True, default="")
    total_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("500.00"),
    )
    materials_advance_pct = serializers.IntegerField(
        min_value=0,
        max_value=MAX_MATERIALS_ADVANCE_PCT,
        required=False,
        default=0,
    )
    customer_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    customer_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    customer_email = serializers.EmailField(required=False, allow_blank=True, default="")
    order = serializers.PrimaryKeyRelatedField(queryset=Order.objects.all(), required=False, allow_null=True)
    inquiry = serializers.PrimaryKeyRelatedField(
        queryset=StorefrontInquiry.objects.all(), required=False, allow_null=True
    )

    def validate(self, attrs):
        slug = (attrs.get("organization_slug") or "").strip()
        org_id = attrs.get("organization_id")
        if not slug and not org_id:
            raise serializers.ValidationError("Provide either organization_slug or organization_id.")
        org = (
            Organization.objects.filter(id=org_id, is_active=True).first()
            if org_id
            else Organization.objects.filter(slug=slug, is_active=True).first()
        )
        if not org:
            raise serializers.ValidationError("Selected artisan organization was not found.")
        attrs["organization"] = org
        return attrs


class EscrowFundResponseSerializer(serializers.Serializer):
    escrow = EscrowTransactionSerializer()
    completion_pin = serializers.CharField(allow_blank=True)
    detail = serializers.CharField()


class EscrowWorkSubmitSerializer(serializers.Serializer):
    completion_notes = serializers.CharField(required=False, allow_blank=True, default="")


class EscrowReleaseSerializer(serializers.Serializer):
    completion_pin = serializers.CharField(max_length=10)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class EscrowDisputeSerializer(serializers.Serializer):
    reason = serializers.CharField()


class EscrowResolveSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["refund_customer", "release_to_artisan"])
    reason = serializers.CharField()

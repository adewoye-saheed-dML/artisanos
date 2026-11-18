from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.models import User
from customers.models import Customer
from measurements.models import MeasurementProfile

from .models import Order, OrderStatusEvent
from .services import ALLOWED_TRANSITIONS, build_measurement_snapshot, compute_payment_status


class OrderStatusEventSerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source="changed_by.full_name", read_only=True, default=None)

    class Meta:
        model = OrderStatusEvent
        fields = ["id", "from_status", "to_status", "notes", "changed_by", "changed_by_name", "created_at"]
        read_only_fields = fields


class OrderListSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "customer",
            "customer_name",
            "garment_type",
            "status",
            "quoted_amount",
            "agreed_amount",
            "deposit_amount",
            "currency",
            "payment_status",
            "expected_completion_date",
            "assigned_to",
            "assigned_to_name",
            "delivery_method",
            "measurement_profile",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class OrderDetailSerializer(OrderListSerializer):
    status_events = OrderStatusEventSerializer(many=True, read_only=True)
    allowed_next_statuses = serializers.SerializerMethodField()

    class Meta(OrderListSerializer.Meta):
        fields = OrderListSerializer.Meta.fields + [
            "description",
            "measurement_snapshot",
            "category_options",
            "customer_instructions",
            "internal_notes",
            "created_by",
            "status_events",
            "allowed_next_statuses",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_allowed_next_statuses(self, obj):
        return sorted(ALLOWED_TRANSITIONS.get(obj.status, set()))


class OrderCreateSerializer(serializers.Serializer):
    customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all())
    garment_type = serializers.CharField(max_length=150)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    measurement_profile = serializers.PrimaryKeyRelatedField(
        queryset=MeasurementProfile.objects.all(),
        required=False,
        allow_null=True,
    )
    status = serializers.ChoiceField(choices=Order.Status.choices, required=False, default=Order.Status.DRAFT)
    quoted_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    agreed_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
    deposit_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        default=Decimal("0.00"),
    )
    currency = serializers.CharField(max_length=3, required=False)
    expected_completion_date = serializers.DateField(required=False, allow_null=True)
    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True,
    )
    customer_instructions = serializers.CharField(required=False, allow_blank=True, default="")
    internal_notes = serializers.CharField(required=False, allow_blank=True, default="")
    category_options = serializers.DictField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        default=dict,
    )
    delivery_method = serializers.ChoiceField(
        choices=Order.DeliveryMethod.choices,
        required=False,
        default=Order.DeliveryMethod.PICKUP,
    )

    def validate_garment_type(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Please specify a garment or item type.")
        return cleaned


class OrderUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = [
            "garment_type",
            "description",
            "measurement_profile",
            "quoted_amount",
            "agreed_amount",
            "deposit_amount",
            "expected_completion_date",
            "assigned_to",
            "category_options",
            "customer_instructions",
            "internal_notes",
            "delivery_method",
        ]

    def validate(self, attrs):
        order = self.instance
        profile = attrs.get("measurement_profile", order.measurement_profile)
        if profile is not None:
            if profile.organization_id != order.organization_id:
                raise serializers.ValidationError({"measurement_profile": "Profile belongs to another organization."})
            if profile.customer_id != order.customer_id:
                raise serializers.ValidationError({"measurement_profile": "Profile must belong to the order's customer."})
        return attrs

    def update(self, instance, validated_data):
        profile_changed = "measurement_profile" in validated_data and validated_data["measurement_profile"] != instance.measurement_profile
        instance = super().update(instance, validated_data)
        instance.payment_status = compute_payment_status(
            instance.quoted_amount,
            instance.agreed_amount,
            instance.deposit_amount,
        )
        if profile_changed and instance.measurement_profile is not None:
            instance.measurement_snapshot = build_measurement_snapshot(instance.measurement_profile)
        instance.save(update_fields=["payment_status", "measurement_snapshot", "updated_at"])
        return instance


class OrderTransitionSerializer(serializers.Serializer):
    to_status = serializers.ChoiceField(choices=Order.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

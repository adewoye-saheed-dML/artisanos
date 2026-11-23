from rest_framework import serializers

from .models import AuditLog, PaymentTransaction, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "currency",
            "max_members",
            "max_customers",
            "max_monthly_measurement_requests",
            "max_products",
            "is_active",
            "display_order",
        ]
        read_only_fields = fields


class SubscriptionSerializer(serializers.ModelSerializer):
    plan = PlanSerializer(read_only=True)

    class Meta:
        model = Subscription
        fields = [
            "id",
            "plan",
            "status",
            "provider",
            "provider_reference",
            "current_period_start",
            "current_period_end",
            "trial_ends_at",
            "updated_at",
        ]
        read_only_fields = fields


class PaymentTransactionSerializer(serializers.ModelSerializer):
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)

    class Meta:
        model = PaymentTransaction
        fields = [
            "id",
            "reference",
            "plan",
            "plan_name",
            "provider",
            "amount",
            "currency",
            "status",
            "verified_at",
            "created_at",
        ]
        read_only_fields = fields


class UsageCounterSerializer(serializers.Serializer):
    used = serializers.IntegerField()
    limit = serializers.IntegerField()


class WorkspaceUsageSerializer(serializers.Serializer):
    members = UsageCounterSerializer()
    customers = UsageCounterSerializer()
    monthly_measurement_requests = UsageCounterSerializer()
    products = UsageCounterSerializer()


class SubscriptionOverviewResponseSerializer(serializers.Serializer):
    subscription = SubscriptionSerializer()
    usage = WorkspaceUsageSerializer()
    transactions = PaymentTransactionSerializer(many=True)
    paystack_configured = serializers.BooleanField()


class CheckoutRequestSerializer(serializers.Serializer):
    plan_code = serializers.SlugField(max_length=40)


class WebhookResponseSerializer(serializers.Serializer):
    processed = serializers.BooleanField()
    detail = serializers.CharField()


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True, default=None)
    organization_name = serializers.CharField(source="organization.name", read_only=True, default=None)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "organization",
            "organization_name",
            "actor",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "reason",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class PlatformAdminActionSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=500)

    def validate_reason(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise serializers.ValidationError("Provide an audit reason (at least 3 characters).")
        return cleaned


class PlatformAdminAssignPlanSerializer(serializers.Serializer):
    plan_code = serializers.SlugField(max_length=40)
    reason = serializers.CharField(max_length=500)


class PlatformAdminOrgSummarySerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.CharField()
    category = serializers.CharField()
    currency = serializers.CharField()
    is_active = serializers.BooleanField()
    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    subscription_status = serializers.CharField()
    member_count = serializers.IntegerField()
    customer_count = serializers.IntegerField()
    order_count = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class PlatformAdminOverviewSerializer(serializers.Serializer):
    total_organizations = serializers.IntegerField()
    active_organizations = serializers.IntegerField()
    suspended_organizations = serializers.IntegerField()
    total_users = serializers.IntegerField()
    total_customers = serializers.IntegerField()
    total_orders = serializers.IntegerField()


class PlatformAdminLocationSyncRequestSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=["baseline", "full_inec"], default="baseline")
    skip_geo = serializers.BooleanField(default=False, required=False)


class PlatformAdminLocationSyncStatusSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=["idle", "running", "succeeded", "failed"])
    mode = serializers.CharField(allow_blank=True)
    last_message = serializers.CharField(allow_blank=True)
    error = serializers.CharField(allow_blank=True)
    started_at = serializers.DateTimeField(allow_null=True)
    finished_at = serializers.DateTimeField(allow_null=True)
    total_states = serializers.IntegerField()
    total_lgas = serializers.IntegerField()
    total_wards = serializers.IntegerField()
    total_polling_units = serializers.IntegerField()
    geolocated_polling_units = serializers.IntegerField()
    is_full_inec_loaded = serializers.BooleanField()

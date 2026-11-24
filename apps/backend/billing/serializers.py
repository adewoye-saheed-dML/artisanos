from rest_framework import serializers

from catalog.models import Product

from .models import AuditLog, MarketplaceBoost, PaymentTransaction, Plan, Subscription


class PlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = Plan
        fields = [
            "id",
            "code",
            "name",
            "description",
            "monthly_price",
            "annual_price",
            "currency",
            "max_members",
            "max_customers",
            "max_monthly_measurement_requests",
            "max_products",
            "max_service_wards",
            "escrow_fee_rate_pct",
            "monthly_free_boosts",
            "is_popular",
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
            "billing_cycle",
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
            "purpose",
            "billing_cycle",
            "plan",
            "plan_name",
            "provider",
            "amount",
            "currency",
            "status",
            "authorization_url",
            "access_code",
            "verified_at",
            "created_at",
        ]
        read_only_fields = fields


class BoostPackageSerializer(serializers.Serializer):
    code = serializers.CharField()
    name = serializers.CharField()
    description = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    duration_days = serializers.IntegerField()
    scope = serializers.CharField()
    badge_label = serializers.CharField()
    eligible_for_plan_credit = serializers.BooleanField()


class MarketplaceBoostSerializer(serializers.ModelSerializer):
    boost_type_label = serializers.CharField(source="get_boost_type_display", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True, default=None)
    payment_reference = serializers.CharField(
        source="payment_transaction.reference", read_only=True, default=None
    )
    authorization_url = serializers.CharField(
        source="payment_transaction.authorization_url", read_only=True, default=""
    )

    class Meta:
        model = MarketplaceBoost
        fields = [
            "id",
            "boost_type",
            "boost_type_label",
            "product",
            "product_name",
            "status",
            "amount",
            "currency",
            "duration_days",
            "starts_at",
            "ends_at",
            "used_plan_credit",
            "payment_reference",
            "authorization_url",
            "created_at",
        ]
        read_only_fields = fields


class BoostCheckoutRequestSerializer(serializers.Serializer):
    boost_type = serializers.ChoiceField(choices=MarketplaceBoost.BoostType.choices)
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(), required=False, allow_null=True
    )
    use_plan_credit = serializers.BooleanField(required=False, default=False)
    callback_url = serializers.URLField(required=False, allow_blank=True, default="")


class BoostCheckoutResponseSerializer(serializers.Serializer):
    boost = MarketplaceBoostSerializer()
    transaction = PaymentTransactionSerializer(allow_null=True)
    detail = serializers.CharField()


class BoostPackagesOverviewSerializer(serializers.Serializer):
    packages = BoostPackageSerializer(many=True)
    monthly_credits_used = serializers.IntegerField()
    monthly_credits_limit = serializers.IntegerField()
    active_boosts = MarketplaceBoostSerializer(many=True)


class UsageCounterSerializer(serializers.Serializer):
    used = serializers.IntegerField()
    limit = serializers.IntegerField()


class WorkspaceUsageSerializer(serializers.Serializer):
    members = UsageCounterSerializer()
    customers = UsageCounterSerializer()
    monthly_measurement_requests = UsageCounterSerializer()
    products = UsageCounterSerializer()
    service_wards = UsageCounterSerializer()
    monthly_boost_credits = UsageCounterSerializer()


class SubscriptionOverviewResponseSerializer(serializers.Serializer):
    subscription = SubscriptionSerializer()
    usage = WorkspaceUsageSerializer()
    transactions = PaymentTransactionSerializer(many=True)
    active_boosts = MarketplaceBoostSerializer(many=True)
    paystack_configured = serializers.BooleanField()


class CheckoutRequestSerializer(serializers.Serializer):
    plan_code = serializers.SlugField(max_length=40)
    billing_cycle = serializers.ChoiceField(
        choices=Subscription.BillingCycle.choices,
        required=False,
        default=Subscription.BillingCycle.MONTHLY,
    )
    callback_url = serializers.URLField(required=False, allow_blank=True, default="")


class VerifyPaymentRequestSerializer(serializers.Serializer):
    reference = serializers.CharField(max_length=120)


class WebhookResponseSerializer(serializers.Serializer):
    processed = serializers.BooleanField()
    detail = serializers.CharField()
    escrow_id = serializers.UUIDField(required=False, allow_null=True)
    completion_pin = serializers.CharField(required=False, allow_blank=True)


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


class PlatformAdminPlanRevenueSerializer(serializers.Serializer):
    plan_code = serializers.CharField()
    plan_name = serializers.CharField()
    monthly_price = serializers.DecimalField(max_digits=12, decimal_places=2)
    active_count = serializers.IntegerField()
    mrr = serializers.DecimalField(max_digits=12, decimal_places=2)


class PlatformAdminRecentRevenueTxSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    reference = serializers.CharField()
    purpose = serializers.CharField()
    organization_name = serializers.CharField()
    label = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    verified_at = serializers.DateTimeField()


class PlatformAdminRevenueSummarySerializer(serializers.Serializer):
    currency = serializers.CharField()
    total_platform_revenue = serializers.DecimalField(max_digits=14, decimal_places=2)
    revenue_30d = serializers.DecimalField(max_digits=14, decimal_places=2)
    estimated_mrr = serializers.DecimalField(max_digits=14, decimal_places=2)
    subscription_revenue_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    subscription_revenue_30d = serializers.DecimalField(max_digits=14, decimal_places=2)
    active_paid_subscriptions = serializers.IntegerField()
    boost_revenue_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    boost_revenue_30d = serializers.DecimalField(max_digits=14, decimal_places=2)
    active_boosts_count = serializers.IntegerField()
    escrow_gmv_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    escrow_held_balance = serializers.DecimalField(max_digits=14, decimal_places=2)
    escrow_fee_revenue_total = serializers.DecimalField(max_digits=14, decimal_places=2)
    escrow_fee_revenue_30d = serializers.DecimalField(max_digits=14, decimal_places=2)
    plan_breakdown = PlatformAdminPlanRevenueSerializer(many=True)
    recent_transactions = PlatformAdminRecentRevenueTxSerializer(many=True)


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

import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, resolve_organization_context
from organizations.models import Membership

from .models import MarketplaceBoost, PaymentTransaction, Plan
from .seed import seed_default_plans
from .serializers import (
    BoostCheckoutRequestSerializer,
    BoostCheckoutResponseSerializer,
    BoostPackagesOverviewSerializer,
    CheckoutRequestSerializer,
    MarketplaceBoostSerializer,
    PaymentTransactionSerializer,
    PlanSerializer,
    SubscriptionOverviewResponseSerializer,
    SubscriptionSerializer,
    VerifyPaymentRequestSerializer,
    WebhookResponseSerializer,
)
from .services import (
    BOOST_PACKAGES,
    get_monthly_boost_credit_usage,
    get_or_create_subscription,
    get_workspace_usage_summary,
    initiate_boost_checkout,
    initiate_plan_checkout,
    process_paystack_webhook_event,
    verify_and_apply_paystack_reference,
    verify_paystack_signature,
)


class PlanListView(APIView):
    """List active ArtisanOS subscription plans (all 4 Nigeria-calibrated tiers)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PlanSerializer(many=True)})
    def get(self, request):
        if Plan.objects.count() < 4:
            seed_default_plans()
        plans = Plan.objects.filter(is_active=True).order_by("display_order", "monthly_price")
        return Response(PlanSerializer(plans, many=True).data)


class SubscriptionOverviewView(APIView):
    """Current workspace subscription, live usage vs entitlements, active boosts, and billing transactions."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: SubscriptionOverviewResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        sub = get_or_create_subscription(org)
        usage = get_workspace_usage_summary(org)
        txs = (
            PaymentTransaction.objects.filter(organization=org)
            .select_related("plan")
            .order_by("-created_at")[:25]
        )
        now = timezone.now()
        active_boosts = (
            MarketplaceBoost.objects.filter(
                organization=org,
                status=MarketplaceBoost.Status.ACTIVE,
                ends_at__gt=now,
            )
            .select_related("product", "payment_transaction")
            .order_by("-ends_at")
        )

        return Response(
            {
                "subscription": SubscriptionSerializer(sub).data,
                "usage": usage,
                "transactions": PaymentTransactionSerializer(txs, many=True).data,
                "active_boosts": MarketplaceBoostSerializer(active_boosts, many=True).data,
                "paystack_configured": bool(getattr(settings, "PAYSTACK_SECRET_KEY", "")),
            }
        )


class SubscriptionCheckoutView(APIView):
    """Initiate a monthly/annual plan change or Paystack checkout transaction (owners & managers only)."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(request=CheckoutRequestSerializer, responses={201: PaymentTransactionSerializer})
    def post(self, request):
        membership = resolve_organization_context(request)
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only organization owners or managers can change plans.")

        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if Plan.objects.count() < 4:
            seed_default_plans()
        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"], is_active=True)

        tx = initiate_plan_checkout(
            organization=membership.organization,
            plan=plan,
            actor=request.user,
            billing_cycle=serializer.validated_data["billing_cycle"],
            callback_url=serializer.validated_data.get("callback_url", ""),
        )
        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class BoostPackageListView(APIView):
    """List available Neighborhood Spotlight & Product/Service Boost packages plus workspace credits."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: BoostPackagesOverviewSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        used, limit = get_monthly_boost_credit_usage(org)
        now = timezone.now()
        active_boosts = (
            MarketplaceBoost.objects.filter(
                organization=org,
                status=MarketplaceBoost.Status.ACTIVE,
                ends_at__gt=now,
            )
            .select_related("product", "payment_transaction")
            .order_by("-ends_at")
        )
        return Response(
            {
                "packages": list(BOOST_PACKAGES.values()),
                "monthly_credits_used": used,
                "monthly_credits_limit": limit,
                "active_boosts": MarketplaceBoostSerializer(active_boosts, many=True).data,
            }
        )


class BoostListView(APIView):
    """List active and historical Marketplace Spotlight boosts for the active workspace."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: MarketplaceBoostSerializer(many=True)})
    def get(self, request):
        org = resolve_organization_context(request).organization
        boosts = (
            MarketplaceBoost.objects.filter(organization=org)
            .select_related("product", "payment_transaction")
            .order_by("-created_at")[:30]
        )
        return Response(MarketplaceBoostSerializer(boosts, many=True).data)


class BoostCheckoutView(APIView):
    """Purchase a Spotlight Boost via Paystack or redeem an included monthly plan credit."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(request=BoostCheckoutRequestSerializer, responses={201: BoostCheckoutResponseSerializer})
    def post(self, request):
        membership = resolve_organization_context(request)
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only organization owners or managers can purchase boosts.")

        serializer = BoostCheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        boost, tx = initiate_boost_checkout(
            organization=membership.organization,
            boost_type=data["boost_type"],
            actor=request.user,
            product=data.get("product"),
            use_plan_credit=data.get("use_plan_credit", False),
            callback_url=data.get("callback_url", ""),
        )
        detail = (
            f"{boost.get_boost_type_display()} is now live for {boost.duration_days} days!"
            if boost.status == MarketplaceBoost.Status.ACTIVE
            else (
                f"Created Paystack checkout {tx.reference} for {tx.currency} {tx.amount}. "
                "Your Spotlight activates automatically once payment is verified."
                if tx
                else "Boost created."
            )
        )
        return Response(
            {
                "boost": MarketplaceBoostSerializer(boost).data,
                "transaction": PaymentTransactionSerializer(tx).data if tx else None,
                "detail": detail,
            },
            status=status.HTTP_201_CREATED,
        )


class PaymentVerifyView(APIView):
    """Server-side Paystack transaction verification after checkout redirect (ART- / BST- / ESC-)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=VerifyPaymentRequestSerializer, responses={200: WebhookResponseSerializer})
    def post(self, request):
        serializer = VerifyPaymentRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = verify_and_apply_paystack_reference(
            serializer.validated_data["reference"],
            actor=request.user,
        )
        return Response(result, status=status.HTTP_200_OK)


class PaystackWebhookView(APIView):
    """Verify Paystack HMAC-SHA512 webhook signature and apply confirmed subscriptions, boosts, and escrows."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=dict,
        responses={
            200: WebhookResponseSerializer,
            401: OpenApiResponse(description="Invalid Paystack signature"),
        },
    )
    def post(self, request):
        signature = request.headers.get("X-Paystack-Signature", "")
        raw_body = request.body
        if not verify_paystack_signature(raw_body, signature):
            return Response({"detail": "Invalid Paystack webhook signature."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return Response({"detail": "Invalid JSON payload."}, status=status.HTTP_400_BAD_REQUEST)

        result = process_paystack_webhook_event(payload)
        return Response(result, status=status.HTTP_200_OK)

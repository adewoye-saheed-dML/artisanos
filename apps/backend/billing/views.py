import json

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, resolve_organization_context
from organizations.models import Membership

from .models import PaymentTransaction, Plan
from .seed import seed_default_plans
from .serializers import (
    CheckoutRequestSerializer,
    PaymentTransactionSerializer,
    PlanSerializer,
    SubscriptionOverviewResponseSerializer,
    SubscriptionSerializer,
    WebhookResponseSerializer,
)
from .services import (
    get_or_create_subscription,
    get_workspace_usage_summary,
    initiate_plan_checkout,
    process_paystack_webhook_event,
    verify_paystack_signature,
)


class PlanListView(APIView):
    """List active ArtisanOS subscription plans."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PlanSerializer(many=True)})
    def get(self, request):
        if not Plan.objects.exists():
            seed_default_plans()
        plans = Plan.objects.filter(is_active=True).order_by("display_order", "monthly_price")
        return Response(PlanSerializer(plans, many=True).data)


class SubscriptionOverviewView(APIView):
    """Current workspace subscription, live usage vs entitlements, and billing transactions."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: SubscriptionOverviewResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        sub = get_or_create_subscription(org)
        usage = get_workspace_usage_summary(org)
        txs = PaymentTransaction.objects.filter(organization=org).select_related("plan").order_by("-created_at")[:20]

        return Response(
            {
                "subscription": SubscriptionSerializer(sub).data,
                "usage": usage,
                "transactions": PaymentTransactionSerializer(txs, many=True).data,
                "paystack_configured": bool(getattr(settings, "PAYSTACK_SECRET_KEY", "")),
            }
        )


class SubscriptionCheckoutView(APIView):
    """Initiate a plan change or Paystack checkout transaction (owners & managers only)."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(request=CheckoutRequestSerializer, responses={201: PaymentTransactionSerializer})
    def post(self, request):
        membership = resolve_organization_context(request)
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only organization owners or managers can change plans.")

        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not Plan.objects.exists():
            seed_default_plans()
        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"], is_active=True)

        tx = initiate_plan_checkout(organization=membership.organization, plan=plan, actor=request.user)
        return Response(PaymentTransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


class PaystackWebhookView(APIView):
    """Verify Paystack HMAC-SHA512 webhook signature and apply confirmed subscription upgrades."""

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

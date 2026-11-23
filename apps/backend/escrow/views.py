from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from organizations.models import Membership

from .models import EscrowTransaction
from .serializers import (
    EscrowCreateSerializer,
    EscrowDisputeSerializer,
    EscrowFundResponseSerializer,
    EscrowReleaseSerializer,
    EscrowTransactionSerializer,
    EscrowWorkSubmitSerializer,
)
from .services import (
    cancel_unfunded_escrow,
    create_escrow_contract,
    dispute_escrow_transaction,
    fund_escrow_transaction,
    release_escrow_to_artisan,
    submit_escrow_work,
)


def _user_escrow_queryset(user):
    org_ids = list(
        Membership.objects.filter(
            user=user,
            status=Membership.Status.ACTIVE,
            organization__is_active=True,
        ).values_list("organization_id", flat=True)
    )
    qs = (
        EscrowTransaction.objects.select_related("organization", "customer_user", "order")
        .prefetch_related("events__actor")
        .order_by("-created_at")
    )
    if user.is_platform_admin:
        return qs
    return qs.filter(Q(customer_user=user) | Q(organization_id__in=org_ids))


class EscrowListCreateView(APIView):
    """List escrow contracts (for customer or artisan workspace) or open a new customer escrow contract."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: EscrowTransactionSerializer(many=True)})
    def get(self, request):
        role_filter = (request.query_params.get("role") or "").strip().lower()
        status_filter = (request.query_params.get("status") or "").strip()
        qs = _user_escrow_queryset(request.user)

        if role_filter == "customer":
            qs = qs.filter(customer_user=request.user)
        elif role_filter == "artisan":
            org_id = request.headers.get("X-Organization-Id")
            if org_id:
                qs = qs.filter(organization_id=org_id)
            else:
                org_ids = list(
                    Membership.objects.filter(
                        user=request.user,
                        status=Membership.Status.ACTIVE,
                    ).values_list("organization_id", flat=True)
                )
                qs = qs.filter(organization_id__in=org_ids)

        if status_filter:
            qs = qs.filter(status=status_filter)

        return Response(
            EscrowTransactionSerializer(qs[:60], many=True, context={"request": request}).data
        )

    @extend_schema(
        request=EscrowCreateSerializer,
        responses={201: EscrowTransactionSerializer},
    )
    def post(self, request):
        serializer = EscrowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        escrow = create_escrow_contract(
            customer_user=request.user,
            organization=data["organization"],
            job_title=data["job_title"],
            job_description=data.get("job_description", ""),
            total_amount=data["total_amount"],
            materials_advance_pct=data.get("materials_advance_pct", 0),
            customer_name=data.get("customer_name", ""),
            customer_phone=data.get("customer_phone", ""),
            customer_email=data.get("customer_email", ""),
            order=data.get("order"),
            inquiry=data.get("inquiry"),
        )
        return Response(
            EscrowTransactionSerializer(escrow, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class EscrowDetailView(APIView):
    """Inspect a single escrow contract and its immutable timeline."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: EscrowTransactionSerializer})
    def get(self, request, escrow_id):
        escrow = get_object_or_404(_user_escrow_queryset(request.user), id=escrow_id)
        return Response(EscrowTransactionSerializer(escrow, context={"request": request}).data)


class EscrowFundView(APIView):
    """Fund an escrow contract (locks funds & returns private 6-digit Completion PIN to the customer)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: EscrowFundResponseSerializer})
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        updated, pin = fund_escrow_transaction(escrow=escrow, actor=request.user, via_webhook=False)
        return Response(
            {
                "escrow": EscrowTransactionSerializer(updated, context={"request": request}).data,
                "completion_pin": pin,
                "detail": (
                    "Funds are now locked safely in ArtisanOS Escrow. Keep your 6-digit Completion PIN "
                    "private and enter it ONLY after inspecting and approving the finished work."
                ),
            }
        )


class EscrowSubmitWorkView(APIView):
    """Artisan marks work completed and invites customer to inspect and release escrow."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EscrowWorkSubmitSerializer,
        responses={200: EscrowTransactionSerializer},
    )
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        serializer = EscrowWorkSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = submit_escrow_work(
            escrow=escrow,
            actor=request.user,
            completion_notes=serializer.validated_data.get("completion_notes", ""),
        )
        return Response(EscrowTransactionSerializer(updated, context={"request": request}).data)


class EscrowReleaseView(APIView):
    """Customer confirms job completion using their private 6-digit PIN and releases full payment."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EscrowReleaseSerializer,
        responses={200: EscrowTransactionSerializer},
    )
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        serializer = EscrowReleaseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = release_escrow_to_artisan(
            escrow=escrow,
            actor=request.user,
            completion_pin=serializer.validated_data["completion_pin"],
            notes=serializer.validated_data.get("notes", ""),
        )
        return Response(EscrowTransactionSerializer(updated, context={"request": request}).data)


class EscrowDisputeView(APIView):
    """Customer freezes escrow funds and raises a dispute if work is unsatisfactory or incomplete."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=EscrowDisputeSerializer,
        responses={200: EscrowTransactionSerializer},
    )
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        serializer = EscrowDisputeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = dispute_escrow_transaction(
            escrow=escrow,
            actor=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(EscrowTransactionSerializer(updated, context={"request": request}).data)


class EscrowCancelView(APIView):
    """Customer cancels an unfunded escrow contract."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={200: EscrowTransactionSerializer})
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        if escrow.customer_user_id != request.user.id:
            raise exceptions.PermissionDenied("Only the customer can cancel this escrow contract.")
        updated = cancel_unfunded_escrow(escrow=escrow, actor=request.user)
        return Response(EscrowTransactionSerializer(updated, context={"request": request}).data)

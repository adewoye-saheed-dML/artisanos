from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import TenantScopedMixin
from customers.models import Customer
from organizations.models import Membership

from .media_services import (
    PHOTO_ACCESS_ROLES,
    get_client_ip,
    permanently_delete_media_asset,
    store_guided_capture,
)
from .models import MeasurementProfile, MeasurementRequest, MeasurementShareLink, MediaAccessLog, MediaAsset
from .serializers import (
    ImportFromShareSerializer,
    MeasurementProfileCreateSerializer,
    MeasurementProfileReviseSerializer,
    MeasurementProfileSerializer,
    MeasurementRequestCreateSerializer,
    MeasurementRequestSerializer,
    MeasurementShareCreatedSerializer,
    MeasurementShareCreateSerializer,
    MeasurementShareLinkSerializer,
    MediaAccessLogSerializer,
    MediaAssetSerializer,
    MediaAssetUploadSerializer,
    PublicFitPassportSerializer,
    PublicMeasurementRequestDetailSerializer,
    PublicMeasurementSubmissionSerializer,
)
from .services import (
    create_measurement_profile,
    create_measurement_request,
    create_measurement_share,
    get_active_share_or_error,
    hash_request_token,
    import_measurement_from_share,
    revise_measurement_profile,
    submit_public_measurement_request,
    verify_measurement_profile,
)


class CustomerMeasurementViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Manage measurement profiles and version history for a specific customer."""

    serializer_class = MeasurementProfileSerializer

    def _get_customer(self) -> Customer:
        org = self.get_organization()
        return get_object_or_404(Customer, id=self.kwargs["customer_id"], organization=org)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MeasurementProfile.objects.none()
        customer = self._get_customer()
        qs = (
            MeasurementProfile.objects.filter(organization=customer.organization, customer=customer)
            .select_related("template_version__template", "created_by", "verified_by")
            .prefetch_related("values__field")
            .order_by("-version_number", "-measured_at")
        )
        if self.request.query_params.get("latest_only") == "true":
            qs = qs.filter(is_latest=True)
        return qs

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        customer = self._get_customer()
        serializer = MeasurementProfileCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile = create_measurement_profile(
            organization=org,
            customer=customer,
            template_version=data["template_version_id"],
            unit_system=data["unit_system"],
            values_payload=data["values"],
            label=data["label"],
            status=data["status"],
            notes=data["notes"],
            measured_at=data.get("measured_at"),
            created_by=request.user,
        )
        profile = self.get_queryset().get(id=profile.id)
        return Response(MeasurementProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        return self._revise(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        return self._revise(request, *args, **kwargs)

    def _revise(self, request, *args, **kwargs):
        profile = self.get_object()
        serializer = MeasurementProfileReviseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        revised = revise_measurement_profile(
            profile=profile,
            actor=request.user,
            unit_system=data.get("unit_system"),
            values_payload=data.get("values"),
            label=data.get("label"),
            notes=data.get("notes"),
            status=data.get("status"),
        )
        revised = self.get_queryset().get(id=revised.id)
        return Response(MeasurementProfileSerializer(revised).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: MeasurementProfileSerializer})
    @action(detail=True, methods=["post"])
    def verify(self, request, customer_id=None, pk=None):
        profile = self.get_object()
        verified = verify_measurement_profile(profile=profile, verifier=request.user)
        verified = self.get_queryset().get(id=verified.id)
        return Response(MeasurementProfileSerializer(verified).data, status=status.HTTP_200_OK)

    @extend_schema(request=ImportFromShareSerializer, responses={201: MeasurementProfileSerializer})
    @action(detail=False, methods=["post"], url_path="import-from-share")
    def import_from_share(self, request, customer_id=None):
        org = self.get_organization()
        customer = self._get_customer()
        serializer = ImportFromShareSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        imported = import_measurement_from_share(
            organization=org,
            customer=customer,
            raw_token=serializer.validated_data["token"],
            imported_by=request.user,
        )
        imported = self.get_queryset().get(id=imported.id)
        return Response(MeasurementProfileSerializer(imported).data, status=status.HTTP_201_CREATED)


class MeasurementRequestViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Create, list, and revoke expiring customer measurement request links."""

    serializer_class = MeasurementRequestSerializer
    filterset_fields = ["status", "customer"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MeasurementRequest.objects.none()
        org = self.get_organization()
        return (
            MeasurementRequest.objects.filter(organization=org)
            .select_related("customer", "template_version__template")
            .order_by("-created_at")
        )

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        serializer = MeasurementRequestCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        req, raw_token = create_measurement_request(
            organization=org,
            customer=data["customer_id"],
            template_version=data["template_version_id"],
            expires_in_hours=data["expires_in_hours"],
            notes=data["notes"],
            created_by=request.user,
        )
        payload = MeasurementRequestSerializer(req).data
        payload["token"] = raw_token
        payload["public_path"] = f"/m/{raw_token}"
        return Response(payload, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        req = self.get_object()
        if req.status != MeasurementRequest.Status.PENDING:
            return Response(
                {"detail": f"Cannot revoke request in '{req.status}' state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        req.status = MeasurementRequest.Status.REVOKED
        req.save(update_fields=["status", "updated_at"])
        return Response(MeasurementRequestSerializer(req).data, status=status.HTTP_200_OK)


class PublicMeasurementSubmissionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    status = serializers.CharField()
    measured_at = serializers.DateTimeField()


class PublicMeasurementRequestView(APIView):
    """Unauthenticated customer measurement portal backed by an expiring random token."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def _get_active_request(self, token: str):
        token_hash = hash_request_token(token)
        req = (
            MeasurementRequest.objects.select_related("organization", "customer", "template_version__template")
            .prefetch_related("template_version__fields")
            .filter(token_hash=token_hash)
            .first()
        )
        if not req:
            return None, Response({"detail": "Measurement link not found."}, status=status.HTTP_404_NOT_FOUND)
        if req.status == MeasurementRequest.Status.REVOKED:
            return None, Response({"detail": "This measurement link has been revoked."}, status=status.HTTP_410_GONE)
        if req.status == MeasurementRequest.Status.SUBMITTED:
            return None, Response({"detail": "Measurements have already been submitted."}, status=status.HTTP_410_GONE)
        if req.status == MeasurementRequest.Status.EXPIRED or req.expires_at <= timezone.now():
            if req.status == MeasurementRequest.Status.PENDING:
                req.status = MeasurementRequest.Status.EXPIRED
                req.save(update_fields=["status", "updated_at"])
            return None, Response({"detail": "This measurement link has expired."}, status=status.HTTP_410_GONE)
        return req, None

    @extend_schema(responses={200: PublicMeasurementRequestDetailSerializer})
    def get(self, request, token: str):
        req, err_response = self._get_active_request(token)
        if err_response:
            return err_response

        first_name = req.customer.full_name.split()[0] if req.customer.full_name else "Customer"
        payload = {
            "organization_name": req.organization.name,
            "customer_first_name": first_name,
            "preferred_unit": req.organization.preferred_unit,
            "template_name": req.template_version.template.name,
            "expires_at": req.expires_at,
            "notes": req.notes,
            "fields": req.template_version.fields.order_by("display_order", "label"),
        }
        serializer = PublicMeasurementRequestDetailSerializer(payload)
        return Response(serializer.data)

    @extend_schema(
        request=PublicMeasurementSubmissionSerializer,
        responses={201: PublicMeasurementSubmissionResponseSerializer},
    )
    def post(self, request, token: str):
        req, err_response = self._get_active_request(token)
        if err_response:
            return err_response

        serializer = PublicMeasurementSubmissionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile = submit_public_measurement_request(
            measurement_request=req,
            unit_system=data["unit_system"],
            values_payload=data["values"],
            notes=data.get("notes", ""),
            consent_granted=data["consent_granted"],
        )
        return Response(
            {
                "detail": "Measurements submitted successfully. Your artisan will review and confirm them.",
                "status": profile.status,
                "measured_at": profile.measured_at,
            },
            status=status.HTTP_201_CREATED,
        )


class MeasurementShareLinkViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Create, list, and revoke consented portable Fit Passport share links."""

    serializer_class = MeasurementShareLinkSerializer
    filterset_fields = ["status", "customer", "profile"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MeasurementShareLink.objects.none()
        org = self.get_organization()
        return (
            MeasurementShareLink.objects.filter(organization=org)
            .select_related("customer", "profile")
            .order_by("-created_at")
        )

    @extend_schema(
        request=MeasurementShareCreateSerializer,
        responses={201: MeasurementShareCreatedSerializer},
    )
    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        serializer = MeasurementShareCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        share, raw_token = create_measurement_share(
            organization=org,
            profile=data["profile_id"],
            created_by=request.user,
            recipient_label=data.get("recipient_label", ""),
            expires_in_days=data["expires_in_days"],
            consent_confirmed=data["consent_confirmed"],
        )
        payload = MeasurementShareLinkSerializer(share).data
        payload["token"] = raw_token
        payload["public_path"] = f"/fit/{raw_token}"
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={200: MeasurementShareLinkSerializer})
    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        share = self.get_object()
        if share.status != MeasurementShareLink.Status.ACTIVE:
            return Response(
                {"detail": f"Cannot revoke share link in '{share.status}' state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        share.status = MeasurementShareLink.Status.REVOKED
        share.save(update_fields=["status", "updated_at"])
        return Response(MeasurementShareLinkSerializer(share).data)


class PublicFitPassportView(APIView):
    """Unauthenticated read-only portable Fit Passport (exposes no internal IDs or contact PII)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: PublicFitPassportSerializer})
    def get(self, request, token: str):
        share = get_active_share_or_error(token)
        share.access_count += 1
        share.last_accessed_at = timezone.now()
        share.save(update_fields=["access_count", "last_accessed_at", "updated_at"])

        profile = share.profile
        first_name = share.customer.full_name.split()[0] if share.customer.full_name else "Client"
        payload = {
            "issuing_organization": share.organization.name,
            "customer_first_name": first_name,
            "profile_label": profile.label,
            "template_name": profile.template_version.template.name,
            "template_category": profile.template_version.template.category,
            "unit_system": profile.unit_system,
            "version_number": profile.version_number,
            "verified_at": profile.verified_at,
            "measured_at": profile.measured_at,
            "expires_at": share.expires_at,
            "values": profile.values.select_related("field").order_by("field__display_order", "field__label"),
        }
        return Response(PublicFitPassportSerializer(payload).data)


class CustomerMediaAssetViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Protected guided-capture reference photos with RBAC, retention expiry, and access logging."""

    serializer_class = MediaAssetSerializer
    parser_classes = [MultiPartParser, FormParser]

    def _require_photo_access(self):
        membership = self.get_membership()
        if membership.role not in PHOTO_ACCESS_ROLES:
            raise exceptions.PermissionDenied(
                "Only owners, managers, and artisans are permitted to access customer reference photos."
            )
        return membership

    def _get_customer(self) -> Customer:
        org = self.get_organization()
        return get_object_or_404(Customer, id=self.kwargs["customer_id"], organization=org)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return MediaAsset.objects.none()
        self._require_photo_access()
        customer = self._get_customer()
        return (
            MediaAsset.objects.filter(organization=customer.organization, customer=customer)
            .select_related("consent_record", "uploaded_by")
            .order_by("-created_at")
        )

    @extend_schema(request=MediaAssetUploadSerializer, responses={201: MediaAssetSerializer})
    def create(self, request, *args, **kwargs):
        self._require_photo_access()
        org = self.get_organization()
        customer = self._get_customer()
        serializer = MediaAssetUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        profile = None
        if data.get("profile_id"):
            profile = get_object_or_404(
                MeasurementProfile,
                id=data["profile_id"],
                organization=org,
                customer=customer,
            )

        asset = store_guided_capture(
            organization=org,
            customer=customer,
            uploaded_file=data["file"],
            view_angle=data["view_angle"],
            photo_consent_granted=data["photo_consent_granted"],
            allow_model_training=data.get("allow_model_training", False),
            quality_metadata=data.get("quality_metadata", {}),
            profile=profile,
            uploaded_by=request.user,
            ip_address=get_client_ip(request),
        )
        return Response(MediaAssetSerializer(asset).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.BINARY, description="Image bytes")})
    @action(detail=True, methods=["get"])
    def content(self, request, customer_id=None, pk=None):
        self._require_photo_access()
        asset = self.get_object()
        if asset.status != MediaAsset.Status.ACTIVE or not asset.file:
            return Response({"detail": "This photo has been deleted or expired."}, status=status.HTTP_410_GONE)
        if asset.retention_expires_at <= timezone.now():
            permanently_delete_media_asset(
                asset=asset,
                actor=None,
                action=MediaAccessLog.Action.PURGED,
                reason="Expired on access check.",
            )
            return Response({"detail": "This photo expired past its retention window."}, status=status.HTTP_410_GONE)

        MediaAccessLog.objects.create(
            organization=asset.organization,
            asset=asset,
            accessed_by=request.user,
            action=MediaAccessLog.Action.VIEWED,
            ip_address=get_client_ip(request),
            notes="Viewed inside customer workspace.",
        )
        resp = FileResponse(asset.file.open("rb"), content_type=asset.content_type)
        resp["Cache-Control"] = "private, no-store"
        return resp

    @extend_schema(responses={200: MediaAccessLogSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def audit(self, request, customer_id=None, pk=None):
        self._require_photo_access()
        asset = self.get_object()
        logs = asset.access_logs.select_related("accessed_by").order_by("-created_at")
        return Response(MediaAccessLogSerializer(logs, many=True).data)

    def destroy(self, request, *args, **kwargs):
        membership = self._require_photo_access()
        asset = self.get_object()
        if (
            membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}
            and asset.uploaded_by_id != request.user.id
        ):
            raise exceptions.PermissionDenied("Only owners, managers, or the uploader can delete photos.")
        deleted = permanently_delete_media_asset(
            asset=asset,
            actor=request.user,
            ip_address=get_client_ip(request),
        )
        return Response(MediaAssetSerializer(deleted).data, status=status.HTTP_200_OK)


class PublicMeasurementRequestPhotoUploadView(APIView):
    """Allow a customer with an active measurement request link to upload consented front/side reference photos."""

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(request=MediaAssetUploadSerializer, responses={201: MediaAssetSerializer})
    def post(self, request, token: str):
        token_hash = hash_request_token(token)
        req = (
            MeasurementRequest.objects.select_related("organization", "customer")
            .filter(token_hash=token_hash)
            .first()
        )
        if not req:
            return Response({"detail": "Measurement link not found."}, status=status.HTTP_404_NOT_FOUND)
        if req.status != MeasurementRequest.Status.PENDING or req.expires_at <= timezone.now():
            return Response({"detail": "This measurement link is no longer active."}, status=status.HTTP_410_GONE)

        serializer = MediaAssetUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        asset = store_guided_capture(
            organization=req.organization,
            customer=req.customer,
            uploaded_file=data["file"],
            view_angle=data["view_angle"],
            photo_consent_granted=data["photo_consent_granted"],
            allow_model_training=False,
            quality_metadata=data.get("quality_metadata", {}),
            measurement_request=req,
            uploaded_by=None,
            ip_address=get_client_ip(request),
        )
        return Response(
            {
                "id": str(asset.id),
                "view_angle": asset.view_angle,
                "status": asset.status,
                "retention_expires_at": asset.retention_expires_at,
                "detail": "Reference photo securely saved for artisan review.",
            },
            status=status.HTTP_201_CREATED,
        )

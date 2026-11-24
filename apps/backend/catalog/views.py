from decimal import Decimal, InvalidOperation

from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, TenantScopedMixin, resolve_organization_context
from locations.models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from orders.serializers import OrderDetailSerializer
from organizations.models import Membership, Organization

from .models import Product, ProductVariant, Storefront, StorefrontInquiry
from .serializers import (
    InventoryAdjustmentInputSerializer,
    InventoryMovementSerializer,
    MarketplaceCategoryCountSerializer,
    MarketplaceProductCardSerializer,
    MarketplaceStorefrontCardSerializer,
    ProductCreateSerializer,
    ProductSerializer,
    ProductVariantSerializer,
    PublicStorefrontInquiryCreateSerializer,
    PublicStorefrontResponseSerializer,
    StorefrontInquirySerializer,
    StorefrontSettingsSerializer,
)
from .services import (
    adjust_inventory,
    compute_organization_proximity,
    convert_inquiry_to_order,
    create_product_with_initial_stock,
    get_or_create_storefront,
    submit_storefront_inquiry,
)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _resolve_target_location_params(request):
    """Resolve optional state/lga/ward/polling_unit query params safely."""
    pu_id = (request.query_params.get("polling_unit") or "").strip()
    ward_id = (request.query_params.get("ward") or "").strip()
    lga_id = (request.query_params.get("lga") or "").strip()
    state_id = (request.query_params.get("state") or "").strip()

    target_pu = (
        PollingUnit.objects.select_related("ward", "ward__lga", "ward__lga__state")
        .filter(id=pu_id)
        .first()
        if pu_id
        else None
    )
    target_ward = (
        NigerianWard.objects.select_related("lga", "lga__state").filter(id=ward_id).first()
        if ward_id
        else (target_pu.ward if target_pu else None)
    )
    target_lga = (
        NigerianLGA.objects.select_related("state").filter(id=lga_id).first()
        if lga_id
        else (target_ward.lga if target_ward else None)
    )
    target_state = (
        NigerianState.objects.filter(id=state_id).first()
        if state_id
        else (target_lga.state if target_lga else None)
    )
    return target_state, target_lga, target_ward, target_pu


class ProductViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Organization-scoped product catalogue and auditable inventory adjustments."""

    filterset_fields = ["status", "product_type", "category"]
    search_fields = ["name", "description", "sku", "category"]
    ordering_fields = ["created_at", "price", "stock_quantity", "name"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Product.objects.none()
        org = self.get_organization()
        return (
            Product.objects.filter(organization=org)
            .prefetch_related("variants")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ProductCreateSerializer
        return ProductSerializer

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        serializer = ProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = create_product_with_initial_stock(
            organization=org,
            created_by=request.user,
            validated_data=serializer.validated_data,
        )
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        membership = self.get_membership()
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only owners or managers can archive products.")
        product = self.get_object()
        product.status = Product.Status.ARCHIVED
        product.save(update_fields=["status", "updated_at"])
        return Response(ProductSerializer(product).data, status=status.HTTP_200_OK)

    @extend_schema(
        request=InventoryAdjustmentInputSerializer,
        responses={201: InventoryMovementSerializer},
    )
    @action(detail=True, methods=["post"], url_path="adjust-inventory")
    def adjust_inventory_action(self, request, pk=None):
        org = self.get_organization()
        product = self.get_object()
        serializer = InventoryAdjustmentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        movement = adjust_inventory(
            organization=org,
            product=product,
            movement_type=data["movement_type"],
            quantity_delta=data["quantity_delta"],
            reason=data["reason"],
            performed_by=request.user,
            variant=data.get("variant"),
        )
        return Response(InventoryMovementSerializer(movement).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: InventoryMovementSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def movements(self, request, pk=None):
        product = self.get_object()
        items = product.inventory_movements.select_related("performed_by", "variant").order_by("-created_at")
        return Response(InventoryMovementSerializer(items, many=True).data)

    @extend_schema(
        request=ProductVariantSerializer,
        responses={201: ProductVariantSerializer},
    )
    @action(detail=True, methods=["post"])
    def variants(self, request, pk=None):
        org = self.get_organization()
        product = self.get_object()
        serializer = ProductVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = ProductVariant.objects.create(
            organization=org,
            product=product,
            **serializer.validated_data,
        )
        return Response(ProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)


class StorefrontSettingsView(APIView):
    """Retrieve or update the active workspace's public storefront profile."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: StorefrontSettingsSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        storefront = get_or_create_storefront(org)
        return Response(StorefrontSettingsSerializer(storefront).data)

    @extend_schema(request=StorefrontSettingsSerializer, responses={200: StorefrontSettingsSerializer})
    def patch(self, request):
        membership = resolve_organization_context(request)
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only owners or managers can edit storefront settings.")
        if (
            request.data.get("is_published") is True
            and not membership.organization.is_verified
        ):
            raise exceptions.PermissionDenied(
                "Complete NIN/CAC KYC verification and await platform approval before publishing your storefront."
            )
        storefront = get_or_create_storefront(membership.organization)
        serializer = StorefrontSettingsSerializer(storefront, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class StorefrontInquiryViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Manage incoming inquiries, goods requests, and work call-outs submitted through the public storefront."""

    serializer_class = StorefrontInquirySerializer
    filterset_fields = ["status", "product", "inquiry_type", "urgency"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StorefrontInquiry.objects.none()
        org = self.get_organization()
        return (
            StorefrontInquiry.objects.filter(organization=org)
            .select_related("product", "customer_ward", "customer_polling_unit", "converted_order")
            .order_by("-created_at")
        )

    @extend_schema(request=None, responses={201: OrderDetailSerializer})
    @action(detail=True, methods=["post"])
    def convert(self, request, pk=None):
        org = self.get_organization()
        inquiry = self.get_object()
        order = convert_inquiry_to_order(organization=org, inquiry=inquiry, actor=request.user)
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)


class PublicStorefrontDetailView(APIView):
    """Unauthenticated public storefront profile and published products/services."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: PublicStorefrontResponseSerializer})
    def get(self, request, slug: str):
        org = get_object_or_404(
            Organization.objects.select_related(
                "state", "lga", "ward", "polling_unit", "kyc_verification"
            ).prefetch_related("service_wards"),
            slug=slug,
            is_active=True,
        )
        storefront = get_or_create_storefront(org)
        if not storefront.is_published:
            return Response({"detail": "This storefront is currently unpublished."}, status=status.HTTP_404_NOT_FOUND)

        products = (
            Product.objects.filter(organization=org, status=Product.Status.PUBLISHED)
            .prefetch_related("variants")
            .order_by("-created_at")
        )
        return Response(
            {
                "storefront": StorefrontSettingsSerializer(storefront).data,
                "products": ProductSerializer(products, many=True).data,
            }
        )


class PublicStorefrontInquiryCreateView(APIView):
    """Submit a buyer order request, service booking, or on-site work call-out on a published storefront."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=PublicStorefrontInquiryCreateSerializer,
        responses={201: StorefrontInquirySerializer},
    )
    def post(self, request, slug: str):
        org = get_object_or_404(Organization, slug=slug, is_active=True)
        storefront = get_or_create_storefront(org)
        if not storefront.is_published:
            return Response({"detail": "This storefront is currently unpublished."}, status=status.HTTP_404_NOT_FOUND)

        serializer = PublicStorefrontInquiryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        inquiry = submit_storefront_inquiry(
            organization=org,
            product=data.get("product"),
            inquiry_type=data.get("inquiry_type"),
            urgency=data.get("urgency", StorefrontInquiry.Urgency.NORMAL),
            buyer_name=data["buyer_name"],
            buyer_phone=data["buyer_phone"],
            buyer_email=data.get("buyer_email", ""),
            customer_ward=data.get("customer_ward"),
            customer_polling_unit=data.get("customer_polling_unit"),
            customer_address=data.get("customer_address", ""),
            preferred_date=data.get("preferred_date"),
            quantity=data.get("quantity", 1),
            budget_amount=data.get("budget_amount"),
            message=data["message"],
        )
        return Response(StorefrontInquirySerializer(inquiry).data, status=status.HTTP_201_CREATED)


class MarketplaceStorefrontListView(APIView):
    """
    Public hyper-local discovery of Nigerian artisans & storefronts.
    Supports searching by Polling Unit, Ward, LGA, State, Craft Category, Availability,
    and smart hierarchical proximity ranking (Same PU -> Same Ward -> Covers Ward -> Same LGA -> Same State).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: MarketplaceStorefrontCardSerializer(many=True)})
    def get(self, request):
        target_state, target_lga, target_ward, target_pu = _resolve_target_location_params(request)
        exact = _truthy(request.query_params.get("exact"))
        available_only = _truthy(request.query_params.get("available_only"))
        callout_only = _truthy(request.query_params.get("callout_only"))
        offering = (request.query_params.get("offering") or "").strip().lower()
        search = (request.query_params.get("search") or "").strip()
        category = (request.query_params.get("category") or "").strip()
        city = (request.query_params.get("city") or "").strip()

        qs = (
            Storefront.objects.select_related(
                "organization",
                "organization__state",
                "organization__lga",
                "organization__ward",
                "organization__polling_unit",
                "organization__kyc_verification",
            )
            .prefetch_related("organization__service_wards")
            .filter(is_published=True, organization__is_active=True)
            .annotate(
                published_product_count=Count(
                    "organization__catalog_product_set",
                    filter=Q(organization__catalog_product_set__status=Product.Status.PUBLISHED),
                    distinct=True,
                ),
                published_service_count=Count(
                    "organization__catalog_product_set",
                    filter=Q(
                        organization__catalog_product_set__status=Product.Status.PUBLISHED,
                        organization__catalog_product_set__product_type=Product.ProductType.SERVICE,
                    ),
                    distinct=True,
                ),
            )
        )

        if search:
            qs = qs.filter(
                Q(organization__name__icontains=search)
                | Q(headline__icontains=search)
                | Q(bio__icontains=search)
                | Q(organization__landmark__icontains=search)
                | Q(organization__city__icontains=search)
                | Q(organization__ward__name__icontains=search)
                | Q(organization__lga__name__icontains=search)
                | Q(organization__polling_unit__name__icontains=search)
                | Q(organization__polling_unit__pu_code__icontains=search)
                | Q(organization__skills__icontains=search)
                | Q(organization__catalog_product_set__name__icontains=search)
            ).distinct()
        if category:
            qs = qs.filter(organization__category=category)
        if city:
            qs = qs.filter(
                Q(organization__city__icontains=city)
                | Q(organization__lga__name__icontains=city)
                | Q(organization__state__name__icontains=city)
            )
        if available_only:
            qs = qs.filter(organization__availability_status=Organization.AvailabilityStatus.AVAILABLE)
        if callout_only:
            qs = qs.filter(organization__available_for_callout=True)
        if offering == "goods":
            qs = qs.filter(organization__offers_goods=True)
        elif offering == "services":
            qs = qs.filter(organization__offers_services=True)

        # Location filtering: strict when exact=true, otherwise filter to at least target_state
        # (and let proximity rank bring Polling Unit -> Ward -> Coverage Ward -> LGA -> State to top)
        has_location_filter = any([target_pu, target_ward, target_lga, target_state])
        if exact:
            if target_pu is not None:
                qs = qs.filter(organization__polling_unit=target_pu)
            elif target_ward is not None:
                qs = qs.filter(
                    Q(organization__ward=target_ward) | Q(organization__service_wards=target_ward)
                ).distinct()
            elif target_lga is not None:
                qs = qs.filter(organization__lga=target_lga)
            elif target_state is not None:
                qs = qs.filter(organization__state=target_state)
        elif target_state is not None:
            qs = qs.filter(
                Q(organization__state=target_state)
                | (Q(organization__service_wards__lga__state=target_state))
            ).distinct()

        from django.utils import timezone
        from billing.models import MarketplaceBoost

        now = timezone.now()
        active_sf_boosts: dict = {}
        for bst in MarketplaceBoost.objects.filter(
            status=MarketplaceBoost.Status.ACTIVE,
            boost_type__in=[
                MarketplaceBoost.BoostType.AREA_7D,
                MarketplaceBoost.BoostType.LGA_30D,
            ],
            ends_at__gt=now,
        ).only("organization_id", "boost_type"):
            badge = (
                "Top Spotlight"
                if bst.boost_type == MarketplaceBoost.BoostType.LGA_30D
                else "Featured Nearby"
            )
            # Upgrade badge to Top Spotlight if org holds both
            if bst.organization_id not in active_sf_boosts or badge == "Top Spotlight":
                active_sf_boosts[bst.organization_id] = badge

        availability_order = {
            Organization.AvailabilityStatus.AVAILABLE: 0,
            Organization.AvailabilityStatus.BUSY: 1,
            Organization.AvailabilityStatus.OFFLINE: 2,
        }

        ranked: list[tuple[tuple, dict]] = []
        for sf in qs[:150]:
            org = sf.organization
            service_wards = list(org.service_wards.all())
            service_ward_ids = {w.id for w in service_wards}
            boost_badge = active_sf_boosts.get(org.id, "")
            is_featured = bool(boost_badge)

            if has_location_filter:
                prox_rank, prox_tier, prox_label, dist_km = compute_organization_proximity(
                    org,
                    target_polling_unit=target_pu,
                    target_ward=target_ward,
                    target_lga=target_lga,
                    target_state=target_state,
                    service_ward_ids=service_ward_ids,
                )
            else:
                prox_rank, prox_tier, prox_label, dist_km = (99, None, None, None)

            row = {
                "organization_name": org.name,
                "slug": org.slug,
                "category": org.category,
                "category_label": org.get_category_display(),
                "phone": org.phone,
                "whatsapp_number": sf.whatsapp_number or org.phone,
                "instagram_handle": sf.instagram_handle,
                "city": org.city,
                "country": org.country,
                "state_id": org.state_id,
                "state_name": org.state.name if org.state else None,
                "lga_id": org.lga_id,
                "lga_name": org.lga.name if org.lga else None,
                "ward_id": org.ward_id,
                "ward_name": org.ward.name if org.ward else None,
                "polling_unit_id": org.polling_unit_id,
                "polling_unit_name": org.polling_unit.name if org.polling_unit else None,
                "polling_unit_code": org.polling_unit.pu_code if org.polling_unit else None,
                "landmark": org.landmark,
                "service_ward_names": [w.name for w in service_wards],
                "headline": sf.headline,
                "bio": sf.bio,
                "skills": org.skills or [],
                "availability_status": org.availability_status,
                "available_for_callout": org.available_for_callout,
                "offers_goods": org.offers_goods,
                "offers_services": org.offers_services,
                "callout_fee": org.callout_fee,
                "currency": org.currency,
                "years_experience": org.years_experience,
                "is_verified": org.is_verified,
                "verification_status": org.verification_status,
                "cac_verified": bool(
                    org.is_verified
                    and getattr(org, "kyc_verification", None)
                    and org.kyc_verification.cac_number
                ),
                "published_product_count": sf.published_product_count,
                "published_service_count": sf.published_service_count,
                "is_featured": is_featured,
                "boost_badge": boost_badge,
                "proximity_tier": prox_tier,
                "proximity_label": prox_label,
                "distance_km": dist_km,
            }
            sort_key = (
                prox_rank,
                0 if is_featured else 1,
                dist_km if dist_km is not None else 99999.0,
                availability_order.get(org.availability_status, 2),
                0 if org.is_verified else 1,
                -sf.published_product_count,
                org.name.lower(),
            )
            ranked.append((sort_key, row))

        ranked.sort(key=lambda item: item[0])
        rows = [row for _, row in ranked[:60]]
        return Response(MarketplaceStorefrontCardSerializer(rows, many=True).data)


class MarketplaceProductListView(APIView):
    """Public discovery of published goods and services across all active storefronts, filterable by Ward/PU."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: MarketplaceProductCardSerializer(many=True)})
    def get(self, request):
        target_state, target_lga, target_ward, target_pu = _resolve_target_location_params(request)
        exact = _truthy(request.query_params.get("exact"))
        has_location_filter = any([target_pu, target_ward, target_lga, target_state])

        qs = (
            Product.objects.select_related(
                "organization",
                "organization__storefront",
                "organization__state",
                "organization__lga",
                "organization__ward",
                "organization__polling_unit",
            )
            .prefetch_related("variants", "organization__service_wards")
            .filter(
                status=Product.Status.PUBLISHED,
                organization__is_active=True,
                organization__storefront__is_published=True,
            )
            .order_by("-created_at")
        )
        search = (request.query_params.get("search") or "").strip()
        product_type = (request.query_params.get("product_type") or "").strip()
        category = (request.query_params.get("category") or "").strip()
        min_price = (request.query_params.get("min_price") or "").strip()
        max_price = (request.query_params.get("max_price") or "").strip()

        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
                | Q(organization__name__icontains=search)
                | Q(organization__ward__name__icontains=search)
                | Q(organization__polling_unit__name__icontains=search)
            )
        if product_type:
            if product_type == "goods":
                qs = qs.filter(
                    product_type__in=[Product.ProductType.READY_MADE, Product.ProductType.MADE_TO_ORDER]
                )
            else:
                qs = qs.filter(product_type=product_type)
        if category:
            qs = qs.filter(organization__category=category)
        if min_price:
            try:
                qs = qs.filter(price__gte=Decimal(min_price))
            except InvalidOperation:
                pass
        if max_price:
            try:
                qs = qs.filter(price__lte=Decimal(max_price))
            except InvalidOperation:
                pass

        if exact:
            if target_pu is not None:
                qs = qs.filter(organization__polling_unit=target_pu)
            elif target_ward is not None:
                qs = qs.filter(
                    Q(organization__ward=target_ward) | Q(organization__service_wards=target_ward)
                ).distinct()
            elif target_lga is not None:
                qs = qs.filter(organization__lga=target_lga)
            elif target_state is not None:
                qs = qs.filter(organization__state=target_state)
        elif target_state is not None:
            qs = qs.filter(
                Q(organization__state=target_state)
                | Q(organization__service_wards__lga__state=target_state)
            ).distinct()

        from django.utils import timezone
        from billing.models import MarketplaceBoost

        now = timezone.now()
        boosted_product_ids = set(
            MarketplaceBoost.objects.filter(
                status=MarketplaceBoost.Status.ACTIVE,
                boost_type=MarketplaceBoost.BoostType.PRODUCT_7D,
                product_id__isnull=False,
                ends_at__gt=now,
            ).values_list("product_id", flat=True)
        )

        items = list(qs[:120])
        for item in items:
            if item.id in boosted_product_ids:
                item._is_featured = True
                item._boost_badge = "Featured Listing"
            else:
                item._is_featured = False
                item._boost_badge = ""

        if has_location_filter:
            ranked_items: list[tuple[tuple, Product]] = []
            for item in items:
                prox_rank, prox_tier, prox_label, dist_km = compute_organization_proximity(
                    item.organization,
                    target_polling_unit=target_pu,
                    target_ward=target_ward,
                    target_lga=target_lga,
                    target_state=target_state,
                )
                item._proximity_tier = prox_tier
                item._proximity_label = prox_label
                item._distance_km = dist_km
                ranked_items.append(
                    (
                        (
                            prox_rank,
                            0 if item._is_featured else 1,
                            dist_km if dist_km is not None else 99999.0,
                            -item.created_at.timestamp(),
                        ),
                        item,
                    )
                )
            ranked_items.sort(key=lambda pair: pair[0])
            items = [item for _, item in ranked_items[:60]]
        else:
            items.sort(key=lambda item: (0 if item._is_featured else 1, -item.created_at.timestamp()))
            items = items[:60]

        return Response(MarketplaceProductCardSerializer(items, many=True).data)


class MarketplaceCategoryListView(APIView):
    """Return all supported artisan trade categories with live published storefront counts."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: MarketplaceCategoryCountSerializer(many=True)})
    def get(self, request):
        counts_map = {
            row["organization__category"]: row["total"]
            for row in Storefront.objects.filter(
                is_published=True,
                organization__is_active=True,
            )
            .values("organization__category")
            .annotate(total=Count("id"))
        }
        payload = [
            {
                "code": code,
                "label": label,
                "artisan_count": counts_map.get(code, 0),
            }
            for code, label in Organization.Category.choices
        ]
        return Response(MarketplaceCategoryCountSerializer(payload, many=True).data)

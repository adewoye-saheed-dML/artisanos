from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, TenantScopedMixin, resolve_organization_context
from organizations.models import Membership, Organization

from .models import Product, ProductVariant, Storefront, StorefrontInquiry
from .serializers import (
    InventoryAdjustmentInputSerializer,
    InventoryMovementSerializer,
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
    create_product_with_initial_stock,
    get_or_create_storefront,
    submit_storefront_inquiry,
)


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
    """Manage incoming inquiries submitted through the workspace's public storefront."""

    serializer_class = StorefrontInquirySerializer
    filterset_fields = ["status", "product"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return StorefrontInquiry.objects.none()
        org = self.get_organization()
        return (
            StorefrontInquiry.objects.filter(organization=org)
            .select_related("product")
            .order_by("-created_at")
        )


class PublicStorefrontDetailView(APIView):
    """Unauthenticated public storefront profile and published products."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: PublicStorefrontResponseSerializer})
    def get(self, request, slug: str):
        org = get_object_or_404(Organization, slug=slug, is_active=True)
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
    """Submit a buyer inquiry on a published public storefront."""

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
            buyer_name=data["buyer_name"],
            buyer_phone=data["buyer_phone"],
            buyer_email=data.get("buyer_email", ""),
            message=data["message"],
        )
        return Response(StorefrontInquirySerializer(inquiry).data, status=status.HTTP_201_CREATED)


class MarketplaceStorefrontListView(APIView):
    """Public discovery of published artisan storefronts across ArtisanOS."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: MarketplaceStorefrontCardSerializer(many=True)})
    def get(self, request):
        qs = (
            Storefront.objects.select_related("organization")
            .filter(is_published=True, organization__is_active=True)
            .annotate(
                published_product_count=Count(
                    "organization__catalog_product_set",
                    filter=Q(organization__catalog_product_set__status=Product.Status.PUBLISHED),
                )
            )
            .order_by("-published_product_count", "organization__name")
        )
        search = (request.query_params.get("search") or "").strip()
        category = (request.query_params.get("category") or "").strip()
        city = (request.query_params.get("city") or "").strip()
        if search:
            qs = qs.filter(
                Q(organization__name__icontains=search)
                | Q(headline__icontains=search)
                | Q(bio__icontains=search)
            )
        if category:
            qs = qs.filter(organization__category=category)
        if city:
            qs = qs.filter(organization__city__icontains=city)

        rows = [
            {
                "organization_name": sf.organization.name,
                "slug": sf.organization.slug,
                "category": sf.organization.category,
                "city": sf.organization.city,
                "country": sf.organization.country,
                "headline": sf.headline,
                "bio": sf.bio,
                "published_product_count": sf.published_product_count,
            }
            for sf in qs[:50]
        ]
        return Response(MarketplaceStorefrontCardSerializer(rows, many=True).data)


class MarketplaceProductListView(APIView):
    """Public discovery of published products across all active, published storefronts."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: MarketplaceProductCardSerializer(many=True)})
    def get(self, request):
        qs = (
            Product.objects.select_related("organization")
            .prefetch_related("variants")
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
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
                | Q(category__icontains=search)
                | Q(organization__name__icontains=search)
            )
        if product_type:
            qs = qs.filter(product_type=product_type)
        if category:
            qs = qs.filter(organization__category=category)

        return Response(MarketplaceProductCardSerializer(qs[:60], many=True).data)

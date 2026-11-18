from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductViewSet, StorefrontInquiryViewSet, StorefrontSettingsView

product_router = DefaultRouter()
product_router.register("", ProductViewSet, basename="product")

inquiry_router = DefaultRouter()
inquiry_router.register("", StorefrontInquiryViewSet, basename="storefront-inquiry")

urlpatterns = [
    path("products/", include(product_router.urls)),
    path("storefront/settings/", StorefrontSettingsView.as_view(), name="storefront-settings"),
    path("storefront/inquiries/", include(inquiry_router.urls)),
]

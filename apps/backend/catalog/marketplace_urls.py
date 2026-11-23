from django.urls import path

from .views import (
    MarketplaceCategoryListView,
    MarketplaceProductListView,
    MarketplaceStorefrontListView,
)

urlpatterns = [
    path("artisans/", MarketplaceStorefrontListView.as_view(), name="marketplace-artisans"),
    path("storefronts/", MarketplaceStorefrontListView.as_view(), name="marketplace-storefronts"),
    path("products/", MarketplaceProductListView.as_view(), name="marketplace-products"),
    path("categories/", MarketplaceCategoryListView.as_view(), name="marketplace-categories"),
]

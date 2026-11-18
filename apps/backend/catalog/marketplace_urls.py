from django.urls import path

from .views import MarketplaceProductListView, MarketplaceStorefrontListView

urlpatterns = [
    path("storefronts/", MarketplaceStorefrontListView.as_view(), name="marketplace-storefronts"),
    path("products/", MarketplaceProductListView.as_view(), name="marketplace-products"),
]

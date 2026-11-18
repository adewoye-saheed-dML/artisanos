from django.urls import path

from .views import PublicStorefrontDetailView, PublicStorefrontInquiryCreateView

urlpatterns = [
    path("<slug:slug>/", PublicStorefrontDetailView.as_view(), name="public-storefront-detail"),
    path("<slug:slug>/inquiries/", PublicStorefrontInquiryCreateView.as_view(), name="public-storefront-inquiry"),
]

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CustomerMeasurementViewSet,
    CustomerMediaAssetViewSet,
    MeasurementRequestViewSet,
    MeasurementShareLinkViewSet,
)

customer_measurement_router = DefaultRouter()
customer_measurement_router.register("", CustomerMeasurementViewSet, basename="customer-measurement")

customer_media_router = DefaultRouter()
customer_media_router.register("", CustomerMediaAssetViewSet, basename="customer-media")

request_router = DefaultRouter()
request_router.register("", MeasurementRequestViewSet, basename="measurement-request")

share_router = DefaultRouter()
share_router.register("", MeasurementShareLinkViewSet, basename="measurement-share")

urlpatterns = [
    path("customers/<uuid:customer_id>/measurements/", include(customer_measurement_router.urls)),
    path("customers/<uuid:customer_id>/media/", include(customer_media_router.urls)),
    path("measurement-requests/", include(request_router.urls)),
    path("measurement-shares/", include(share_router.urls)),
]

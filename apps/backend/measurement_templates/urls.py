from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import MeasurementTemplateViewSet

router = DefaultRouter()
router.register("", MeasurementTemplateViewSet, basename="measurement-template")

urlpatterns = [
    path("", include(router.urls)),
]

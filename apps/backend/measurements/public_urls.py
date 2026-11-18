from django.urls import path

from .views import PublicMeasurementRequestPhotoUploadView, PublicMeasurementRequestView

urlpatterns = [
    path("<str:token>/", PublicMeasurementRequestView.as_view(), name="public-measurement-request"),
    path(
        "<str:token>/photos/",
        PublicMeasurementRequestPhotoUploadView.as_view(),
        name="public-measurement-request-photos",
    ),
]

from django.urls import path

from .views import (
    LGAListView,
    LocationDetectView,
    LocationEnsureView,
    LocationStatsView,
    LocationUnifiedSearchView,
    PollingUnitListView,
    StateListView,
    WardListView,
)

urlpatterns = [
    path("states/", StateListView.as_view(), name="location-states"),
    path("lgas/", LGAListView.as_view(), name="location-lgas"),
    path("wards/", WardListView.as_view(), name="location-wards"),
    path("polling-units/", PollingUnitListView.as_view(), name="location-polling-units"),
    path("search/", LocationUnifiedSearchView.as_view(), name="location-search"),
    path("stats/", LocationStatsView.as_view(), name="location-stats"),
    path("detect/", LocationDetectView.as_view(), name="location-detect"),
    path("ensure/", LocationEnsureView.as_view(), name="location-ensure"),
]

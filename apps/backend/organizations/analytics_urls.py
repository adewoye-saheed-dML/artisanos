from django.urls import path

from .analytics_views import AnalyticsOverviewView, CustomerCsvExportView, OrderCsvExportView

urlpatterns = [
    path("overview/", AnalyticsOverviewView.as_view(), name="analytics-overview"),
    path("export/customers/", CustomerCsvExportView.as_view(), name="analytics-export-customers"),
    path("export/orders/", OrderCsvExportView.as_view(), name="analytics-export-orders"),
]

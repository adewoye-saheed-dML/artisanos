from django.urls import path

from .views import PlanListView, SubscriptionCheckoutView, SubscriptionOverviewView

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="subscription-plans"),
    path("overview/", SubscriptionOverviewView.as_view(), name="subscription-overview"),
    path("checkout/", SubscriptionCheckoutView.as_view(), name="subscription-checkout"),
]

from django.urls import path

from .views import (
    BoostCheckoutView,
    BoostListView,
    BoostPackageListView,
    PaymentVerifyView,
    PlanListView,
    SubscriptionCheckoutView,
    SubscriptionOverviewView,
)

urlpatterns = [
    path("plans/", PlanListView.as_view(), name="subscription-plans"),
    path("overview/", SubscriptionOverviewView.as_view(), name="subscription-overview"),
    path("checkout/", SubscriptionCheckoutView.as_view(), name="subscription-checkout"),
    path("verify/", PaymentVerifyView.as_view(), name="subscription-verify-payment"),
    path("boost-packages/", BoostPackageListView.as_view(), name="boost-packages"),
    path("boosts/", BoostListView.as_view(), name="boost-list"),
    path("boosts/checkout/", BoostCheckoutView.as_view(), name="boost-checkout"),
]

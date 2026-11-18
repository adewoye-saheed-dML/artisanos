from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ProductionBoardView, ProductionTaskViewSet, SeedOrderChecklistView

router = DefaultRouter()
router.register("tasks", ProductionTaskViewSet, basename="production-task")

urlpatterns = [
    path("board/", ProductionBoardView.as_view(), name="production-board"),
    path("orders/<uuid:order_id>/seed-checklist/", SeedOrderChecklistView.as_view(), name="production-seed-checklist"),
    path("", include(router.urls)),
]

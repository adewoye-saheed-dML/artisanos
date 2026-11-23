import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from accounts.models import User
from billing.models import Plan
from locations.models import NigerianLGA, NigerianState, PollingUnit
from measurement_templates.models import MeasurementTemplate


@pytest.mark.django_db
def test_bootstrap_deploy_zero_shell_idempotent(monkeypatch):
    monkeypatch.setenv("DJANGO_SUPERUSER_EMAIL", "admin@artisanos.test")
    monkeypatch.setenv("DJANGO_SUPERUSER_PASSWORD", "StrongAdminPass2026!")
    monkeypatch.setenv("DJANGO_SUPERUSER_FULL_NAME", "Render Free Admin")
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)

    call_command("bootstrap_deploy")

    assert MeasurementTemplate.objects.count() >= 3
    assert Plan.objects.count() >= 3
    assert NigerianState.objects.count() == 37
    assert NigerianLGA.objects.count() >= 774
    assert PollingUnit.objects.count() >= 50

    admin_user = User.objects.get(email="admin@artisanos.test")
    assert admin_user.is_superuser is True
    assert admin_user.is_staff is True
    assert admin_user.is_platform_admin is True
    assert admin_user.full_name == "Render Free Admin"
    assert admin_user.check_password("StrongAdminPass2026!")

    # Running a second time is completely idempotent (fast-path cold start)
    call_command("bootstrap_deploy")
    assert User.objects.filter(email="admin@artisanos.test").count() == 1


@pytest.mark.django_db
def test_platform_admin_locations_sync_endpoints():
    regular = User.objects.create_user(
        email="user@artisanos.test",
        password="UserPass1234!",
        full_name="Regular User",
    )
    admin = User.objects.create_superuser(
        email="platform@artisanos.test",
        password="AdminPass1234!",
        full_name="Platform Admin",
    )

    client = APIClient()
    client.force_authenticate(user=regular)
    assert client.get("/api/v1/platform-admin/locations/status/").status_code == 403
    assert client.post("/api/v1/platform-admin/locations/sync/", {"mode": "baseline"}).status_code == 403

    client.force_authenticate(user=admin)
    status_res = client.get("/api/v1/platform-admin/locations/status/")
    assert status_res.status_code == 200
    assert "total_states" in status_res.data
    assert "state" in status_res.data

    sync_res = client.post(
        "/api/v1/platform-admin/locations/sync/",
        {"mode": "baseline"},
        format="json",
    )
    assert sync_res.status_code == 200
    assert sync_res.data["state"] == "succeeded"
    assert sync_res.data["total_states"] == 37
    assert sync_res.data["total_lgas"] >= 774
    assert sync_res.data["total_polling_units"] >= 50

    root_res = APIClient().get("/")
    assert root_res.status_code == 200
    assert root_res.data["status"] == "ok"
    assert root_res.data["health"] == "/api/v1/health/"

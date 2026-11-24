import pytest

from locations.services import clear_location_lookup_caches


@pytest.fixture(autouse=True)
def _disable_live_external_location_lookups(settings):
    """
    Keep unit tests fast, deterministic, and offline by default.
    Tests that verify GRID3 / Google Maps / Nominatim / Paystack live HTTP calls explicitly
    override these flags and mock the HTTP layer.
    """
    settings.LOCATION_EXTERNAL_LOOKUP_ENABLED = False
    settings.PAYSTACK_LIVE_API_ENABLED = False
    clear_location_lookup_caches()
    yield
    clear_location_lookup_caches()

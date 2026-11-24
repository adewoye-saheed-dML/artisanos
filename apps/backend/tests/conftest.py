import pytest

from locations.services import clear_location_lookup_caches


@pytest.fixture(autouse=True)
def _disable_live_external_location_lookups(settings):
    """
    Keep unit tests fast, deterministic, and offline by default.
    Tests that verify GRID3 / Google Maps / Nominatim behavior explicitly override
    LOCATION_EXTERNAL_LOOKUP_ENABLED=True and mock the HTTP layer.
    """
    settings.LOCATION_EXTERNAL_LOOKUP_ENABLED = False
    clear_location_lookup_caches()
    yield
    clear_location_lookup_caches()

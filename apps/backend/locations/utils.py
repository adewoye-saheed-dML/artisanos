import math
from decimal import Decimal


def haversine_km(
    lat1: Decimal | float | None,
    lon1: Decimal | float | None,
    lat2: Decimal | float | None,
    lon2: Decimal | float | None,
) -> float | None:
    """Return great-circle distance in kilometres between two WGS84 coordinate pairs."""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    r = 6371.0
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    d_phi = math.radians(float(lat2) - float(lat1))
    d_lambda = math.radians(float(lon2) - float(lon1))
    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)

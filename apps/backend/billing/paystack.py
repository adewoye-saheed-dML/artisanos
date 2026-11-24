import json
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings


def is_paystack_live_enabled() -> bool:
    return bool(
        getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
        and getattr(settings, "PAYSTACK_LIVE_API_ENABLED", True)
    )


def _paystack_request(method: str, path: str, payload: dict | None = None, timeout: float = 8.0) -> dict | None:
    secret = getattr(settings, "PAYSTACK_SECRET_KEY", "").strip()
    if not secret or not getattr(settings, "PAYSTACK_LIVE_API_ENABLED", True):
        return None

    base_url = getattr(settings, "PAYSTACK_API_BASE_URL", "https://api.paystack.co").rstrip("/")
    url = f"{base_url}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method.upper(),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "User-Agent": "ArtisanOS-Nigeria/2.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status not in {200, 201}:
                return None
            parsed = json.loads(resp.read().decode("utf-8"))
            if isinstance(parsed, dict) and parsed.get("status") is True:
                return parsed.get("data") or {}
            return None
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None


def initialize_paystack_transaction(
    *,
    email: str,
    amount: Decimal,
    reference: str,
    currency: str = "NGN",
    callback_url: str = "",
    metadata: dict | None = None,
) -> dict | None:
    """
    Initialize a Paystack Hosted Checkout transaction and return authorization_url + access_code.
    Returns None gracefully when Paystack live API is unconfigured or unreachable so callers can
    still record verifiable pending transactions.
    """
    if not email:
        return None
    amount_minor = int((Decimal(str(amount)) * Decimal("100")).quantize(Decimal("1")))
    if amount_minor <= 0:
        return None

    body: dict = {
        "email": email.strip(),
        "amount": amount_minor,
        "reference": reference,
        "currency": currency.upper(),
    }
    if callback_url:
        body["callback_url"] = callback_url
    if metadata:
        body["metadata"] = metadata

    data = _paystack_request("POST", "/transaction/initialize", body)
    if not data:
        return None
    return {
        "authorization_url": (data.get("authorization_url") or "").strip(),
        "access_code": (data.get("access_code") or "").strip(),
        "reference": (data.get("reference") or reference).strip(),
    }


def verify_paystack_transaction(reference: str) -> dict | None:
    """Server-side Paystack transaction verification (`GET /transaction/verify/{reference}`)."""
    cleaned = (reference or "").strip()
    if not cleaned:
        return None
    return _paystack_request("GET", f"/transaction/verify/{cleaned}")

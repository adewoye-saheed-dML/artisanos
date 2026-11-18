"""
Phase 4 integration boundary for camera-assisted measurements.

Camera/AI estimation is NOT implemented in Phase 0/1.
All production measurements must be entered manually or confirmed by a human.
"""

from django.conf import settings


class CameraMeasurementNotEnabledError(RuntimeError):
    """Raised when camera estimation is invoked while the feature flag is off."""


def get_camera_measurement_status() -> dict:
    return {
        "enabled": bool(getattr(settings, "FEATURE_CAMERA_MEASUREMENTS", False)),
        "stage": "not_implemented_phase_4_boundary",
    }


def estimate_measurements_from_images(*args, **kwargs):
    """Future Phase 4 boundary: pose/calibration estimation requires explicit validation."""
    raise CameraMeasurementNotEnabledError(
        "AI/camera-assisted measurement estimation is disabled in Phase 0/1."
    )

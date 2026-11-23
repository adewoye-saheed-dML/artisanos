from django.conf import settings
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class ApiRootResponseSerializer(serializers.Serializer):
    service = serializers.CharField()
    status = serializers.CharField()
    health = serializers.CharField()
    docs = serializers.CharField()
    schema = serializers.CharField()
    admin = serializers.CharField()


class ApiRootView(APIView):
    """Friendly API index at / so direct browser visits and root probes receive 200 OK."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: ApiRootResponseSerializer})
    def get(self, request):
        return Response(
            {
                "service": "ArtisanOS API",
                "status": "ok",
                "health": "/api/v1/health/",
                "docs": "/api/v1/docs/",
                "schema": "/api/v1/schema/",
                "admin": "/admin/",
            },
            status=status.HTTP_200_OK,
        )


class HealthFeaturesSerializer(serializers.Serializer):
    camera_measurements = serializers.BooleanField()


class HealthCheckResponseSerializer(serializers.Serializer):
    status = serializers.CharField()
    database = serializers.CharField()
    features = HealthFeaturesSerializer()


class HealthCheckView(APIView):
    """Health check endpoint verifying PostgreSQL connectivity and feature flags."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: HealthCheckResponseSerializer, 503: HealthCheckResponseSerializer})
    def get(self, request):
        db_ok = True
        db_error = None
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception as exc:  # pragma: no cover - defensive health diagnostic
            db_ok = False
            db_error = str(exc)

        payload = {
            "status": "ok" if db_ok else "degraded",
            "database": "connected" if db_ok else f"error: {db_error}",
            "features": {
                "camera_measurements": settings.FEATURE_CAMERA_MEASUREMENTS,
            },
        }
        code = status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=code)

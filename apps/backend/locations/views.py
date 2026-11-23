from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Storefront

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from .serializers import (
    LocationDetectInputSerializer,
    LocationEnsureInputSerializer,
    LocationResolvedResponseSerializer,
    LocationSearchResponseSerializer,
    LocationStatsSerializer,
    NigerianLGASerializer,
    NigerianStateSerializer,
    NigerianWardSerializer,
    PollingUnitSerializer,
)
from .services import detect_nigerian_location, ensure_ward_and_polling_unit


class StateListView(APIView):
    """List Nigerian states (36 States + FCT Abuja)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: NigerianStateSerializer(many=True)})
    def get(self, request):
        qs = NigerianState.objects.all()
        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(code__icontains=search))
        return Response(NigerianStateSerializer(qs, many=True).data)


class LGAListView(APIView):
    """List Local Government Areas, optionally filtered by state."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: NigerianLGASerializer(many=True)})
    def get(self, request):
        qs = NigerianLGA.objects.select_related("state").all()
        state_id = (request.query_params.get("state") or "").strip()
        search = (request.query_params.get("search") or "").strip()
        if state_id:
            qs = qs.filter(state_id=state_id)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(state__name__icontains=search))
        return Response(NigerianLGASerializer(qs[:200], many=True).data)


class WardListView(APIView):
    """List Nigerian Electoral Wards (Registration Areas) filtered by LGA or state."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: NigerianWardSerializer(many=True)})
    def get(self, request):
        qs = NigerianWard.objects.select_related("lga", "lga__state").all()
        lga_id = (request.query_params.get("lga") or "").strip()
        state_id = (request.query_params.get("state") or "").strip()
        search = (request.query_params.get("search") or "").strip()
        if lga_id:
            qs = qs.filter(lga_id=lga_id)
        if state_id:
            qs = qs.filter(lga__state_id=state_id)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(lga__name__icontains=search)
                | Q(lga__state__name__icontains=search)
            )
        return Response(NigerianWardSerializer(qs[:200], many=True).data)


class PollingUnitListView(APIView):
    """List hyper-local Nigerian Polling Units filtered by ward, LGA, state, or search query."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: PollingUnitSerializer(many=True)})
    def get(self, request):
        qs = PollingUnit.objects.select_related("ward", "ward__lga", "ward__lga__state").all()
        ward_id = (request.query_params.get("ward") or "").strip()
        lga_id = (request.query_params.get("lga") or "").strip()
        state_id = (request.query_params.get("state") or "").strip()
        search = (request.query_params.get("search") or "").strip()
        if ward_id:
            qs = qs.filter(ward_id=ward_id)
        if lga_id:
            qs = qs.filter(ward__lga_id=lga_id)
        if state_id:
            qs = qs.filter(ward__lga__state_id=state_id)
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(pu_code__icontains=search)
                | Q(landmark__icontains=search)
                | Q(ward__name__icontains=search)
                | Q(ward__lga__name__icontains=search)
            )
        limit = 600 if ward_id else 200
        return Response(PollingUnitSerializer(qs[:limit], many=True).data)


class LocationUnifiedSearchView(APIView):
    """Fast autocomplete search across Nigerian Wards and Polling Units (supports 176k+ rows)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: LocationSearchResponseSerializer})
    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 2:
            return Response({"wards": [], "polling_units": []})

        state_id = (request.query_params.get("state") or "").strip()
        lga_id = (request.query_params.get("lga") or "").strip()
        ward_id = (request.query_params.get("ward") or "").strip()

        wards_qs = NigerianWard.objects.select_related("lga", "lga__state").filter(
            Q(name__icontains=query)
            | Q(lga__name__icontains=query)
            | Q(lga__state__name__icontains=query)
        )
        pus_qs = PollingUnit.objects.select_related("ward", "ward__lga", "ward__lga__state").filter(
            Q(name__icontains=query)
            | Q(pu_code__icontains=query)
            | Q(landmark__icontains=query)
            | Q(ward__name__icontains=query)
        )
        if state_id:
            wards_qs = wards_qs.filter(lga__state_id=state_id)
            pus_qs = pus_qs.filter(ward__lga__state_id=state_id)
        if lga_id:
            wards_qs = wards_qs.filter(lga_id=lga_id)
            pus_qs = pus_qs.filter(ward__lga_id=lga_id)
        if ward_id:
            pus_qs = pus_qs.filter(ward_id=ward_id)

        wards = wards_qs.order_by("name")[:12]
        polling_units = pus_qs.order_by("name")[:20]
        return Response(
            {
                "wards": NigerianWardSerializer(wards, many=True).data,
                "polling_units": PollingUnitSerializer(polling_units, many=True).data,
            }
        )


class LocationStatsView(APIView):
    """Return live Nigerian INEC geographic dataset coverage counts."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: LocationStatsSerializer})
    def get(self, request):
        total_pus = PollingUnit.objects.count()
        payload = {
            "total_states": NigerianState.objects.count(),
            "total_lgas": NigerianLGA.objects.count(),
            "total_wards": NigerianWard.objects.count(),
            "total_polling_units": total_pus,
            "geolocated_polling_units": PollingUnit.objects.filter(
                latitude__isnull=False, longitude__isnull=False
            ).count(),
            "is_full_inec_loaded": total_pus >= 100000,
        }
        return Response(LocationStatsSerializer(payload).data)


def _count_nearby_artisans(state, lga, ward) -> int:
    qs = Storefront.objects.filter(is_published=True, organization__is_active=True)
    if ward is not None:
        ward_hits = qs.filter(
            Q(organization__ward=ward)
            | Q(organization__service_wards=ward)
            | Q(organization__lga=ward.lga)
        ).distinct().count()
        if ward_hits > 0:
            return ward_hits
    if lga is not None:
        lga_hits = qs.filter(organization__lga=lga).count()
        if lga_hits > 0:
            return lga_hits
    if state is not None:
        return qs.filter(organization__state=state).count()
    return 0


class LocationDetectView(APIView):
    """Auto-detect Nigerian State -> LGA -> Ward -> Polling Unit from GPS coordinates or address hints."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=LocationDetectInputSerializer,
        responses={200: LocationResolvedResponseSerializer},
    )
    def post(self, request):
        serializer = LocationDetectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = detect_nigerian_location(
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            state_name=data.get("state_name", ""),
            lga_name=data.get("lga_name", ""),
            ward_name=data.get("ward_name", ""),
            polling_unit_name=data.get("polling_unit_name", ""),
            landmark=data.get("landmark", ""),
        )
        nearby_count = _count_nearby_artisans(result["state"], result["lga"], result["ward"])
        payload = {
            "state": NigerianStateSerializer(result["state"]).data if result["state"] else None,
            "lga": NigerianLGASerializer(result["lga"]).data if result["lga"] else None,
            "ward": NigerianWardSerializer(result["ward"]).data if result["ward"] else None,
            "polling_unit": PollingUnitSerializer(result["polling_unit"]).data if result["polling_unit"] else None,
            "landmark": result["landmark"],
            "match_source": result["match_source"],
            "distance_km": result["distance_km"],
            "nearby_artisan_count": nearby_count,
        }
        return Response(payload, status=status.HTTP_200_OK)


class LocationEnsureView(APIView):
    """
    Find or register a Ward and optional Polling Unit inside any of Nigeria's 774 LGAs
    so users & artisans anywhere in Nigeria can immediately map their exact neighborhood.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        request=LocationEnsureInputSerializer,
        responses={200: LocationResolvedResponseSerializer},
    )
    def post(self, request):
        serializer = LocationEnsureInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        lga = data["lga"]
        ward, pu = ensure_ward_and_polling_unit(
            lga=lga,
            ward_name=data["ward_name"],
            polling_unit_name=data.get("polling_unit_name", ""),
            landmark=data.get("landmark", ""),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
        )
        nearby_count = _count_nearby_artisans(lga.state, lga, ward)
        payload = {
            "state": NigerianStateSerializer(lga.state).data,
            "lga": NigerianLGASerializer(lga).data,
            "ward": NigerianWardSerializer(ward).data,
            "polling_unit": PollingUnitSerializer(pu).data if pu else None,
            "landmark": (pu.landmark if pu else data.get("landmark", "")),
            "match_source": "community_mapped",
            "distance_km": None,
            "nearby_artisan_count": nearby_count,
        }
        return Response(payload, status=status.HTTP_200_OK)

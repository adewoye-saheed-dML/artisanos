from rest_framework import serializers

from .models import NigerianLGA, NigerianState, NigerianWard, PollingUnit


class NigerianStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NigerianState
        fields = ["id", "name", "code", "geopolitical_zone"]
        read_only_fields = fields


class NigerianLGASerializer(serializers.ModelSerializer):
    state_name = serializers.CharField(source="state.name", read_only=True)

    class Meta:
        model = NigerianLGA
        fields = ["id", "state", "state_name", "name", "code"]
        read_only_fields = fields


class NigerianWardSerializer(serializers.ModelSerializer):
    lga_name = serializers.CharField(source="lga.name", read_only=True)
    state_id = serializers.UUIDField(source="lga.state_id", read_only=True)
    state_name = serializers.CharField(source="lga.state.name", read_only=True)

    class Meta:
        model = NigerianWard
        fields = ["id", "lga", "lga_name", "state_id", "state_name", "name", "code"]
        read_only_fields = fields


class PollingUnitSerializer(serializers.ModelSerializer):
    ward_name = serializers.CharField(source="ward.name", read_only=True)
    lga_id = serializers.UUIDField(source="ward.lga_id", read_only=True)
    lga_name = serializers.CharField(source="ward.lga.name", read_only=True)
    state_id = serializers.UUIDField(source="ward.lga.state_id", read_only=True)
    state_name = serializers.CharField(source="ward.lga.state.name", read_only=True)

    class Meta:
        model = PollingUnit
        fields = [
            "id",
            "ward",
            "ward_name",
            "lga_id",
            "lga_name",
            "state_id",
            "state_name",
            "name",
            "pu_code",
            "landmark",
            "latitude",
            "longitude",
        ]
        read_only_fields = fields


class LocationSearchResponseSerializer(serializers.Serializer):
    wards = NigerianWardSerializer(many=True)
    polling_units = PollingUnitSerializer(many=True)


class LocationDetectInputSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    state_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    lga_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    ward_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    polling_unit_name = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    landmark = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")


class LocationEnsureInputSerializer(serializers.Serializer):
    lga = serializers.PrimaryKeyRelatedField(queryset=NigerianLGA.objects.select_related("state").all())
    ward_name = serializers.CharField(max_length=150)
    polling_unit_name = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    landmark = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)

    def validate_ward_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Ward name must be at least 2 characters.")
        return cleaned


class LocationResolvedResponseSerializer(serializers.Serializer):
    state = NigerianStateSerializer(allow_null=True)
    lga = NigerianLGASerializer(allow_null=True)
    ward = NigerianWardSerializer(allow_null=True)
    polling_unit = PollingUnitSerializer(allow_null=True)
    landmark = serializers.CharField(allow_blank=True)
    match_source = serializers.CharField()
    distance_km = serializers.FloatField(allow_null=True)
    nearby_artisan_count = serializers.IntegerField()


class LocationStatsSerializer(serializers.Serializer):
    total_states = serializers.IntegerField()
    total_lgas = serializers.IntegerField()
    total_wards = serializers.IntegerField()
    total_polling_units = serializers.IntegerField()
    geolocated_polling_units = serializers.IntegerField()
    is_full_inec_loaded = serializers.BooleanField()

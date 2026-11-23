from decimal import Decimal

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.services import get_or_create_storefront
from locations.models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from locations.services import detect_nigerian_location, ensure_ward_and_polling_unit
from organizations.kyc_services import (
    normalize_and_validate_cac,
    normalize_and_validate_nin,
    normalize_and_validate_nuban,
    submit_artisan_kyc,
)
from organizations.models import ArtisanVerification, Membership, Organization
from organizations.serializers import MembershipSummarySerializer
from organizations.services import (
    create_organization_with_owner,
    resolve_nigerian_location_hierarchy,
)

from .models import User


class UserSerializer(serializers.ModelSerializer):
    memberships = serializers.SerializerMethodField()
    state_name = serializers.CharField(source="state.name", read_only=True, default=None)
    lga_name = serializers.CharField(source="lga.name", read_only=True, default=None)
    ward_name = serializers.CharField(source="ward.name", read_only=True, default=None)
    polling_unit_name = serializers.CharField(source="polling_unit.name", read_only=True, default=None)
    polling_unit_code = serializers.CharField(source="polling_unit.pu_code", read_only=True, default=None)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "phone",
            "state",
            "state_name",
            "lga",
            "lga_name",
            "ward",
            "ward_name",
            "polling_unit",
            "polling_unit_name",
            "polling_unit_code",
            "landmark",
            "latitude",
            "longitude",
            "is_platform_admin",
            "created_at",
            "memberships",
        ]
        read_only_fields = fields

    @extend_schema_field(MembershipSummarySerializer(many=True))
    def get_memberships(self, obj):
        qs = (
            Membership.objects.select_related(
                "organization",
                "organization__state",
                "organization__lga",
                "organization__ward",
                "organization__polling_unit",
            )
            .prefetch_related("organization__service_wards")
            .filter(
                user=obj,
                status=Membership.Status.ACTIVE,
                organization__is_active=True,
            )
        )
        return MembershipSummarySerializer(qs, many=True).data


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    # Optional initial workspace creation during onboarding
    organization_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    organization_category = serializers.ChoiceField(
        choices=Organization.Category.choices,
        required=False,
        default=Organization.Category.TAILOR,
    )
    currency = serializers.CharField(max_length=3, required=False, default="NGN")
    preferred_unit = serializers.ChoiceField(
        choices=Organization.UnitSystem.choices,
        required=False,
        default=Organization.UnitSystem.CM,
    )
    city = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    country = serializers.CharField(max_length=100, required=False, allow_blank=True, default="Nigeria")
    state = serializers.PrimaryKeyRelatedField(
        queryset=NigerianState.objects.all(), required=False, allow_null=True
    )
    lga = serializers.PrimaryKeyRelatedField(
        queryset=NigerianLGA.objects.all(), required=False, allow_null=True
    )
    ward = serializers.PrimaryKeyRelatedField(
        queryset=NigerianWard.objects.all(), required=False, allow_null=True
    )
    polling_unit = serializers.PrimaryKeyRelatedField(
        queryset=PollingUnit.objects.all(), required=False, allow_null=True
    )
    # Optional custom Ward / Polling Unit names (auto-registered under any of Nigeria's 774 LGAs)
    ward_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    polling_unit_name = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    landmark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    available_for_callout = serializers.BooleanField(required=False, default=True)
    callout_fee = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.00"),
        required=False,
        allow_null=True,
    )
    skills = serializers.ListField(
        child=serializers.CharField(max_length=60),
        required=False,
        default=list,
    )
    # Strict Artisan KYC fields (NIN required for every artisan workspace; CAC & bank validated)
    nin = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    government_id_type = serializers.ChoiceField(
        choices=ArtisanVerification.GovernmentIdType.choices,
        required=False,
        default=ArtisanVerification.GovernmentIdType.NIN_SLIP,
    )
    cac_number = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    cac_business_name = serializers.CharField(max_length=160, required=False, allow_blank=True, default="")
    guarantor_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    guarantor_phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    bank_name = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    bank_account_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    bank_account_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate(self, attrs):
        org_name = (attrs.get("organization_name") or "").strip()
        if org_name:
            # Strict anti-scam registration: every artisan MUST supply a valid 11-digit NIN
            nin = (attrs.get("nin") or "").strip()
            if not nin:
                raise serializers.ValidationError(
                    {"nin": "A valid 11-digit Nigerian NIN is required to register as an artisan."}
                )
            attrs["nin"] = normalize_and_validate_nin(nin)
            if attrs.get("cac_number"):
                attrs["cac_number"] = normalize_and_validate_cac(attrs["cac_number"])
            if attrs.get("bank_account_number"):
                attrs["bank_account_number"] = normalize_and_validate_nuban(attrs["bank_account_number"])
        return attrs

    def validate_email(self, value: str) -> str:
        normalized = value.strip().lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return normalized

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_currency(self, value: str) -> str:
        cleaned = value.strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise serializers.ValidationError("Currency must be a 3-letter ISO code (e.g. NGN, USD, GBP).")
        return cleaned

    @transaction.atomic
    def create(self, validated_data):
        org_name = validated_data.pop("organization_name", "").strip()
        org_category = validated_data.pop("organization_category", Organization.Category.TAILOR)
        currency = validated_data.pop("currency", "NGN")
        preferred_unit = validated_data.pop("preferred_unit", Organization.UnitSystem.CM)
        city = validated_data.pop("city", "")
        country = validated_data.pop("country", "Nigeria")
        state = validated_data.pop("state", None)
        lga = validated_data.pop("lga", None)
        ward = validated_data.pop("ward", None)
        polling_unit = validated_data.pop("polling_unit", None)
        ward_name = validated_data.pop("ward_name", "").strip()
        polling_unit_name = validated_data.pop("polling_unit_name", "").strip()
        latitude = validated_data.pop("latitude", None)
        longitude = validated_data.pop("longitude", None)
        landmark = validated_data.pop("landmark", "").strip()
        available_for_callout = validated_data.pop("available_for_callout", True)
        callout_fee = validated_data.pop("callout_fee", None)
        skills = validated_data.pop("skills", [])
        nin = validated_data.pop("nin", "")
        government_id_type = validated_data.pop(
            "government_id_type", ArtisanVerification.GovernmentIdType.NIN_SLIP
        )
        cac_number = validated_data.pop("cac_number", "")
        cac_business_name = validated_data.pop("cac_business_name", "")
        guarantor_name = validated_data.pop("guarantor_name", "")
        guarantor_phone = validated_data.pop("guarantor_phone", "")
        bank_name = validated_data.pop("bank_name", "")
        bank_account_number = validated_data.pop("bank_account_number", "")
        bank_account_name = validated_data.pop("bank_account_name", "")

        # Validate explicit hierarchy first if IDs were provided
        state, lga, ward, polling_unit = resolve_nigerian_location_hierarchy(
            state=state,
            lga=lga,
            ward=ward,
            polling_unit=polling_unit,
        )

        # If user supplied custom ward_name / polling_unit_name under an LGA, organically map it
        if lga is not None and (ward is None or (polling_unit is None and polling_unit_name)):
            if ward is not None and polling_unit_name:
                ward, polling_unit = ensure_ward_and_polling_unit(
                    lga=lga,
                    ward_name=ward.name,
                    polling_unit_name=polling_unit_name,
                    landmark=landmark,
                    latitude=latitude,
                    longitude=longitude,
                )
            elif ward_name:
                ward, polling_unit = ensure_ward_and_polling_unit(
                    lga=lga,
                    ward_name=ward_name,
                    polling_unit_name=polling_unit_name,
                    landmark=landmark,
                    latitude=latitude,
                    longitude=longitude,
                )
        # If coordinates were supplied without an explicit ward/polling unit, auto-detect now
        elif ward is None and latitude is not None and longitude is not None:
            detected = detect_nigerian_location(
                latitude=latitude,
                longitude=longitude,
                ward_name=ward_name,
                polling_unit_name=polling_unit_name,
                landmark=landmark,
            )
            state = detected["state"] or state
            lga = detected["lga"] or lga
            ward = detected["ward"] or ward
            polling_unit = detected["polling_unit"] or polling_unit
            if not landmark and detected["landmark"]:
                landmark = detected["landmark"]

        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"].strip(),
            phone=validated_data.get("phone", "").strip(),
            state=state,
            lga=lga,
            ward=ward,
            polling_unit=polling_unit,
            landmark=landmark,
            latitude=latitude,
            longitude=longitude,
        )

        if org_name:
            org, _ = create_organization_with_owner(
                user=user,
                name=org_name,
                category=org_category,
                currency=currency,
                preferred_unit=preferred_unit,
                city=city,
                country=country,
                state=state,
                lga=lga,
                ward=ward,
                polling_unit=polling_unit,
                landmark=landmark,
                available_for_callout=available_for_callout,
                callout_fee=callout_fee,
                skills=skills,
                email=user.email,
                phone=user.phone,
            )
            # Submit strict KYC dossier (NIN/CAC/guarantor/payout bank) — storefront stays unpublished until verified!
            submit_artisan_kyc(
                organization=org,
                submitted_by=user,
                nin=nin,
                government_id_type=government_id_type,
                cac_number=cac_number,
                cac_business_name=cac_business_name,
                guarantor_name=guarantor_name,
                guarantor_phone=guarantor_phone,
                bank_name=bank_name,
                bank_account_number=bank_account_number,
                bank_account_name=bank_account_name,
            )

        return user


class UserLocationUpdateSerializer(serializers.Serializer):
    state = serializers.PrimaryKeyRelatedField(
        queryset=NigerianState.objects.all(), required=False, allow_null=True
    )
    lga = serializers.PrimaryKeyRelatedField(
        queryset=NigerianLGA.objects.all(), required=False, allow_null=True
    )
    ward = serializers.PrimaryKeyRelatedField(
        queryset=NigerianWard.objects.all(), required=False, allow_null=True
    )
    polling_unit = serializers.PrimaryKeyRelatedField(
        queryset=PollingUnit.objects.all(), required=False, allow_null=True
    )
    ward_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    polling_unit_name = serializers.CharField(max_length=220, required=False, allow_blank=True, default="")
    landmark = serializers.CharField(max_length=200, required=False, allow_blank=True, default="")
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]
        user = authenticate(request=self.context.get("request"), username=email, password=password)
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        attrs["user"] = user
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

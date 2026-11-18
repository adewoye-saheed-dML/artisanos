from rest_framework import serializers

from .models import Customer


class CustomerSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    class Meta:
        model = Customer
        fields = [
            "id",
            "organization",
            "full_name",
            "phone",
            "email",
            "address",
            "preferred_contact_method",
            "notes",
            "is_archived",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "organization", "created_by", "created_by_name", "created_at", "updated_at"]

    def validate_full_name(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Customer name must be at least 2 characters.")
        return cleaned

    def validate_phone(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 5:
            raise serializers.ValidationError("Please provide a valid phone number.")
        return cleaned

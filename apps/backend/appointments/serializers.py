from rest_framework import exceptions, serializers

from organizations.models import Membership

from .models import Appointment


class AppointmentSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    order_number = serializers.CharField(source="order.order_number", read_only=True, default=None)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "organization",
            "customer",
            "customer_name",
            "order",
            "order_number",
            "appointment_type",
            "title",
            "scheduled_at",
            "duration_minutes",
            "location",
            "status",
            "assigned_to",
            "assigned_to_name",
            "notes",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "customer_name",
            "order_number",
            "assigned_to_name",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Appointment title must be at least 2 characters.")
        return cleaned

    def validate_duration_minutes(self, value: int) -> int:
        if value < 10 or value > 480:
            raise serializers.ValidationError("Duration must be between 10 and 480 minutes.")
        return value

    def validate(self, attrs):
        org = self.context["organization"]
        customer = attrs.get("customer") or (self.instance.customer if self.instance else None)
        order = attrs.get("order", self.instance.order if self.instance else None)
        assigned_to = attrs.get("assigned_to", self.instance.assigned_to if self.instance else None)

        if customer is None:
            raise serializers.ValidationError({"customer": "Customer is required."})
        if customer.organization_id != org.id:
            raise exceptions.PermissionDenied("Customer does not belong to the active organization.")
        if order is not None:
            if order.organization_id != org.id:
                raise exceptions.PermissionDenied("Order does not belong to the active organization.")
            if order.customer_id != customer.id:
                raise serializers.ValidationError({"order": "Order must belong to the selected customer."})
        if assigned_to is not None:
            is_member = Membership.objects.filter(
                organization=org,
                user=assigned_to,
                status=Membership.Status.ACTIVE,
            ).exists()
            if not is_member:
                raise serializers.ValidationError(
                    {"assigned_to": "Assigned user must be an active member of this organization."}
                )
        return attrs

    def create(self, validated_data):
        org = self.context["organization"]
        user = self.context["request"].user
        return Appointment.objects.create(organization=org, created_by=user, **validated_data)

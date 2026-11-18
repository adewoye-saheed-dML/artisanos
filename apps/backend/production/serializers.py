from rest_framework import serializers

from accounts.models import User
from orders.models import Order

from .models import ProductionTask
from .services import apply_task_status_timestamp, validate_task_relations


class ProductionTaskSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source="order.order_number", read_only=True)
    assigned_to_name = serializers.CharField(source="assigned_to.full_name", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    class Meta:
        model = ProductionTask
        fields = [
            "id",
            "organization",
            "order",
            "order_number",
            "title",
            "stage",
            "status",
            "is_alteration",
            "assigned_to",
            "assigned_to_name",
            "due_date",
            "notes",
            "display_order",
            "completed_at",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "organization",
            "order_number",
            "assigned_to_name",
            "completed_at",
            "created_by",
            "created_by_name",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise serializers.ValidationError("Task title must be at least 2 characters.")
        return cleaned

    def validate(self, attrs):
        org = self.context["organization"]
        order = attrs.get("order") or (self.instance.order if self.instance else None)
        assigned_to = attrs.get("assigned_to", self.instance.assigned_to if self.instance else None)
        if order is None:
            raise serializers.ValidationError({"order": "Order is required."})
        validate_task_relations(organization=org, order=order, assigned_to=assigned_to)
        return attrs

    def create(self, validated_data):
        org = self.context["organization"]
        user = self.context["request"].user
        task = ProductionTask(organization=org, created_by=user, **validated_data)
        apply_task_status_timestamp(task, task.status)
        task.save()
        return task

    def update(self, instance, validated_data):
        new_status = validated_data.get("status", instance.status)
        for attr, val in validated_data.items():
            setattr(instance, attr, val)
        apply_task_status_timestamp(instance, new_status)
        instance.save()
        return instance


class ProductionBoardOrderSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    order_number = serializers.CharField()
    customer = serializers.UUIDField()
    customer_name = serializers.CharField()
    garment_type = serializers.CharField()
    status = serializers.CharField()
    expected_completion_date = serializers.DateField(allow_null=True)
    assigned_to = serializers.UUIDField(allow_null=True)
    assigned_to_name = serializers.CharField(allow_null=True)
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    alteration_tasks = serializers.IntegerField()
    allowed_next_statuses = serializers.ListField(child=serializers.CharField())


class ProductionBoardColumnSerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField()
    orders = ProductionBoardOrderSerializer(many=True)


class ProductionBoardResponseSerializer(serializers.Serializer):
    columns = ProductionBoardColumnSerializer(many=True)

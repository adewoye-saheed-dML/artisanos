from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id",
            "organization",
            "event_type",
            "title",
            "message",
            "link_path",
            "is_read",
            "created_at",
        ]
        read_only_fields = fields


class NotificationListResponseSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()
    results = NotificationSerializer(many=True)

from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, resolve_organization_context

from .models import Notification
from .serializers import NotificationListResponseSerializer, NotificationSerializer


class ReadAllResponseSerializer(serializers.Serializer):
    updated = serializers.IntegerField()


class NotificationListView(APIView):
    """List workspace notifications visible to the current member plus unread count."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: NotificationListResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        qs = Notification.objects.filter(
            organization=org,
        ).filter(Q(recipient__isnull=True) | Q(recipient=request.user))

        unread_count = qs.filter(is_read=False).count()
        items = qs.order_by("-created_at")[:50]
        return Response(
            {
                "unread_count": unread_count,
                "results": NotificationSerializer(items, many=True).data,
            }
        )


class NotificationMarkReadView(APIView):
    """Mark a single notification as read."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(request=None, responses={200: NotificationSerializer})
    def post(self, request, notification_id):
        org = resolve_organization_context(request).organization
        notif = get_object_or_404(
            Notification.objects.filter(organization=org).filter(
                Q(recipient__isnull=True) | Q(recipient=request.user)
            ),
            id=notification_id,
        )
        if not notif.is_read:
            notif.is_read = True
            notif.save(update_fields=["is_read", "updated_at"])
        return Response(NotificationSerializer(notif).data)


class NotificationMarkAllReadView(APIView):
    """Mark all visible workspace notifications as read."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(request=None, responses={200: ReadAllResponseSerializer})
    def post(self, request):
        org = resolve_organization_context(request).organization
        updated = (
            Notification.objects.filter(organization=org, is_read=False)
            .filter(Q(recipient__isnull=True) | Q(recipient=request.user))
            .update(is_read=True)
        )
        return Response({"updated": updated}, status=status.HTTP_200_OK)

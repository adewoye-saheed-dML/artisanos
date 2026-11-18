from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import exceptions, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import User
from accounts.serializers import UserSerializer
from core.authentication import set_auth_cookies

from .models import Membership, Organization, OrganizationInvitation
from .serializers import (
    MembershipMemberSerializer,
    MembershipUpdateSerializer,
    OrganizationCreateSerializer,
    OrganizationInvitationCreatedSerializer,
    OrganizationInvitationCreateSerializer,
    OrganizationInvitationSerializer,
    OrganizationSerializer,
    PublicInvitationAcceptSerializer,
    PublicInvitationDetailSerializer,
)
from .services import (
    accept_invitation,
    create_invitation,
    get_active_invitation_or_error,
    update_member,
)


class OrganizationViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Manage organizations, team memberships, and invitations."""

    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Organization.objects.none()
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__status=Membership.Status.ACTIVE,
            is_active=True,
        ).distinct()

    def get_serializer_class(self):
        if self.action == "create":
            return OrganizationCreateSerializer
        return OrganizationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        output = OrganizationSerializer(org, context={"request": request}).data
        return Response(output, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        org = self.get_object()
        membership = Membership.objects.filter(
            user=self.request.user,
            organization=org,
            status=Membership.Status.ACTIVE,
        ).first()
        if not membership or membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only organization owners or managers can update workspace settings.")
        serializer.save()

    @extend_schema(responses={200: MembershipMemberSerializer(many=True)})
    @action(detail=True, methods=["get"])
    def members(self, request, pk=None):
        org = self.get_object()
        memberships = Membership.objects.select_related("user").filter(organization=org).order_by("created_at")
        return Response(MembershipMemberSerializer(memberships, many=True).data)

    @extend_schema(
        parameters=[OpenApiParameter("member_id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
        request=MembershipUpdateSerializer,
        responses={200: MembershipMemberSerializer},
    )
    @action(detail=True, methods=["patch"], url_path=r"members/(?P<member_id>[^/.]+)")
    def update_member_detail(self, request, pk=None, member_id=None):
        org = self.get_object()
        target = get_object_or_404(Membership.objects.select_related("user"), id=member_id, organization=org)
        serializer = MembershipUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = update_member(
            organization=org,
            target_membership=target,
            actor=request.user,
            role=serializer.validated_data.get("role"),
            status=serializer.validated_data.get("status"),
        )
        return Response(MembershipMemberSerializer(updated).data)

    @extend_schema(
        request=OrganizationInvitationCreateSerializer,
        responses={
            200: OrganizationInvitationSerializer(many=True),
            201: OrganizationInvitationCreatedSerializer,
        },
    )
    @action(detail=True, methods=["get", "post"])
    def invitations(self, request, pk=None):
        org = self.get_object()
        if request.method == "GET":
            invites = (
                OrganizationInvitation.objects.filter(organization=org)
                .select_related("invited_by")
                .order_by("-created_at")
            )
            return Response(OrganizationInvitationSerializer(invites, many=True).data)

        serializer = OrganizationInvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite, raw_token = create_invitation(
            organization=org,
            actor=request.user,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            expires_in_days=serializer.validated_data["expires_in_days"],
        )
        payload = OrganizationInvitationSerializer(invite).data
        payload["token"] = raw_token
        payload["invite_path"] = f"/invite/{raw_token}"
        return Response(payload, status=status.HTTP_201_CREATED)

    @extend_schema(
        parameters=[OpenApiParameter("invite_id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
        request=None,
        responses={200: OrganizationInvitationSerializer},
    )
    @action(detail=True, methods=["post"], url_path=r"invitations/(?P<invite_id>[^/.]+)/revoke")
    def revoke_invitation(self, request, pk=None, invite_id=None):
        org = self.get_object()
        actor_membership = Membership.objects.filter(
            user=request.user,
            organization=org,
            status=Membership.Status.ACTIVE,
        ).first()
        if not actor_membership or actor_membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only owners or managers can revoke invitations.")

        invite = get_object_or_404(OrganizationInvitation, id=invite_id, organization=org)
        if invite.status != OrganizationInvitation.Status.PENDING:
            return Response(
                {"detail": f"Cannot revoke invitation in '{invite.status}' state."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        invite.status = OrganizationInvitation.Status.REVOKED
        invite.save(update_fields=["status", "updated_at"])
        return Response(OrganizationInvitationSerializer(invite).data)


class PublicInvitationDetailView(APIView):
    """Inspect a team invitation token without requiring authentication."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        responses={
            200: PublicInvitationDetailSerializer,
            404: OpenApiResponse(description="Invitation not found"),
            400: OpenApiResponse(description="Invitation expired or revoked"),
        }
    )
    def get(self, request, token: str):
        invitation = get_active_invitation_or_error(token)
        account_exists = User.objects.filter(email__iexact=invitation.email).exists()
        serializer = PublicInvitationDetailSerializer(
            {
                "organization_name": invitation.organization.name,
                "organization_category": invitation.organization.category,
                "email": invitation.email,
                "role": invitation.role,
                "expires_at": invitation.expires_at,
                "invited_by_name": invitation.invited_by.full_name if invitation.invited_by else None,
                "account_exists": account_exists,
            }
        )
        return Response(serializer.data)


class PublicInvitationAcceptView(APIView):
    """Accept an invitation (signed-in matching user, existing user with password, or new user signup)."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=PublicInvitationAcceptSerializer,
        responses={200: UserSerializer},
    )
    def post(self, request, token: str):
        serializer = PublicInvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user, membership = accept_invitation(
            raw_token=token,
            authenticated_user=request.user if request.user.is_authenticated else None,
            full_name=data.get("full_name", ""),
            password=data.get("password", ""),
            phone=data.get("phone", ""),
        )
        refresh = RefreshToken.for_user(user)
        get_token(request)
        response = Response(
            {
                "user": UserSerializer(user).data,
                "organization_id": str(membership.organization_id),
                "role": membership.role,
            },
            status=status.HTTP_200_OK,
        )
        set_auth_cookies(response, str(refresh.access_token), str(refresh))
        return response

from django.conf import settings
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from core.authentication import clear_auth_cookies, enforce_csrf, set_auth_cookies

from .serializers import LoginSerializer, PasswordResetRequestSerializer, RegisterSerializer, UserSerializer


class CsrfResponseSerializer(serializers.Serializer):
    csrfToken = serializers.CharField()


class AuthUserResponseSerializer(serializers.Serializer):
    user = UserSerializer()


class DetailMessageSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True)


def _issue_auth_response(request, user, status_code=status.HTTP_200_OK):
    refresh = RefreshToken.for_user(user)
    get_token(request)
    response = Response({"user": UserSerializer(user).data}, status=status_code)
    set_auth_cookies(response, str(refresh.access_token), str(refresh))
    return response


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfCookieView(APIView):
    """Issues a CSRF cookie for browser clients."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(responses={200: CsrfResponseSerializer})
    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class RegisterView(APIView):
    """Register a new artisan user and optionally create an initial organization."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=RegisterSerializer, responses={201: AuthUserResponseSerializer})
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return _issue_auth_response(request, user, status_code=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Authenticate with email/password and set HttpOnly JWT cookies."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=LoginSerializer, responses={200: AuthUserResponseSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return _issue_auth_response(request, user, status_code=status.HTTP_200_OK)


class RefreshView(APIView):
    """Rotate refresh cookie and issue a fresh access_token cookie."""

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=RefreshRequestSerializer, responses={200: DetailMessageSerializer})
    def post(self, request):
        cookie_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH)
        if cookie_refresh:
            enforce_csrf(request)
        raw_refresh = cookie_refresh or request.data.get("refresh")
        if not raw_refresh:
            return Response({"detail": "Refresh token not provided."}, status=status.HTTP_401_UNAUTHORIZED)

        try:
            old_refresh = RefreshToken(raw_refresh)
            user_id = old_refresh["user_id"]
            from .models import User

            user = User.objects.get(id=user_id, is_active=True)
            old_refresh.blacklist()
            new_refresh = RefreshToken.for_user(user)
        except (TokenError, KeyError, User.DoesNotExist):
            response = Response({"detail": "Invalid or expired refresh token."}, status=status.HTTP_401_UNAUTHORIZED)
            clear_auth_cookies(response)
            return response

        response = Response({"detail": "Token refreshed."}, status=status.HTTP_200_OK)
        set_auth_cookies(response, str(new_refresh.access_token), str(new_refresh))
        return response


class LogoutView(APIView):
    """Blacklist refresh token (if present) and clear auth cookies."""

    permission_classes = [AllowAny]

    @extend_schema(request=RefreshRequestSerializer, responses={200: DetailMessageSerializer})
    def post(self, request):
        raw_refresh = request.COOKIES.get(settings.AUTH_COOKIE_REFRESH) or request.data.get("refresh")
        if request.COOKIES.get(settings.AUTH_COOKIE_ACCESS) or request.COOKIES.get(settings.AUTH_COOKIE_REFRESH):
            enforce_csrf(request)
        if raw_refresh:
            try:
                RefreshToken(raw_refresh).blacklist()
            except TokenError:
                pass
        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        clear_auth_cookies(response)
        return response


class MeView(APIView):
    """Return current authenticated user and active memberships."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AuthUserResponseSerializer})
    def get(self, request):
        get_token(request)
        return Response({"user": UserSerializer(request.user).data})


class PasswordResetRequestView(APIView):
    """
    Foundation endpoint for password reset requests.
    Email delivery is deferred to Phase 2 notifications.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(request=PasswordResetRequestSerializer, responses={202: DetailMessageSerializer})
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "detail": "If an account exists for that email, password reset instructions will be dispatched once email delivery is configured."
            },
            status=status.HTTP_202_ACCEPTED,
        )

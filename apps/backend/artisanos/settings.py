import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Load root .env if present, then backend .env
load_dotenv(BASE_DIR.parent.parent / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)


def env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-change-me-in-production")
DEBUG = env_bool("DJANGO_DEBUG", True)

ALLOWED_HOSTS = [
    h.strip()
    for h in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "rest_framework_simplejwt.token_blacklist",
    # ArtisanOS apps
    "core",
    "accounts",
    "organizations",
    "customers",
    "measurement_templates",
    "measurements",
    "orders",
    "production",
    "appointments",
    "catalog",
    "notifications",
    "billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "artisanos.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "artisanos.wsgi.application"
ASGI_APPLICATION = "artisanos.asgi.application"

# PostgreSQL database configuration
DEFAULT_DATABASE_URL = (
    f"postgres://{os.getenv('POSTGRES_USER', 'artisanos')}:"
    f"{os.getenv('POSTGRES_PASSWORD', 'artisanos_dev_password')}@"
    f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
    f"{os.getenv('POSTGRES_PORT', '5432')}/"
    f"{os.getenv('POSTGRES_DB', 'artisanos')}"
)

DATABASES = {
    "default": dj_database_url.parse(
        os.getenv("ARTISANOS_DATABASE_URL") or os.getenv("DATABASE_URL") or DEFAULT_DATABASE_URL,
        conn_max_age=600,
    )
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "core.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

AUTH_COOKIE_ACCESS = "access_token"
AUTH_COOKIE_REFRESH = "refresh_token"
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", not DEBUG)
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-organization-id",
    "x-requested-with",
]

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if o.strip()
]
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

SPECTACULAR_SETTINGS = {
    "TITLE": "ArtisanOS API",
    "DESCRIPTION": "Multi-tenant SaaS API for measurement-based artisan businesses.",
    "VERSION": "0.2.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "ENUM_NAME_OVERRIDES": {
        "OrganizationCategoryEnum": "organizations.models.Organization.Category",
        "UnitSystemEnum": "organizations.models.Organization.UnitSystem",
        "MembershipRoleEnum": "organizations.models.Membership.Role",
        "MembershipStatusEnum": "organizations.models.Membership.Status",
        "InvitationStatusEnum": "organizations.models.OrganizationInvitation.Status",
        "TemplateCategoryEnum": "measurement_templates.models.MeasurementTemplate.Category",
        "MeasurementProfileStatusEnum": "measurements.models.MeasurementProfile.Status",
        "MeasurementRequestStatusEnum": "measurements.models.MeasurementRequest.Status",
        "MeasurementShareStatusEnum": "measurements.models.MeasurementShareLink.Status",
        "MediaAssetStatusEnum": "measurements.models.MediaAsset.Status",
        "OrderStatusEnum": "orders.models.Order.Status",
        "ProductionTaskStatusEnum": "production.models.ProductionTask.Status",
        "AppointmentStatusEnum": "appointments.models.Appointment.Status",
        "ProductStatusEnum": "catalog.models.Product.Status",
        "StorefrontInquiryStatusEnum": "catalog.models.StorefrontInquiry.Status",
        "SubscriptionStatusEnum": "billing.models.Subscription.Status",
        "PaymentTransactionStatusEnum": "billing.models.PaymentTransaction.Status",
    },
}

# Future AI / Camera measurement feature flag (Phase 4)
FEATURE_CAMERA_MEASUREMENTS = env_bool("FEATURE_CAMERA_MEASUREMENTS", False)

# Paystack webhook verification secret (leave blank until live keys are configured)
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")

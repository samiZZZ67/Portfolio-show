import os
import sys
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def read_env_text(path):
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def load_env_file(path):
    if not path.exists() or not path.is_file():
        return

    env_text = read_env_text(path).replace("\x00", "")
    for raw_line in env_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not key:
            continue
        os.environ.setdefault(key, value)


# Load .env from backend/ directory first, then project root for backward compat
for env_candidate in (BASE_DIR / ".env", BASE_DIR / "local.env", BASE_DIR.parent / ".env"):
    load_env_file(env_candidate)


def csv_env(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def first_env(*names, default=""):
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return default


def resolve_env_aliases(*names):
    resolved = {}
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            resolved[name] = value

    unique_values = {value for value in resolved.values() if value}
    if len(unique_values) > 1:
        return "", resolved, f"Conflicting values were found for: {', '.join(resolved.keys())}."

    return (next(iter(unique_values)) if unique_values else ""), resolved, ""


SECRET_KEY = os.environ.get("SECRET_KEY", "unsafe-secret")
DEBUG = os.environ.get("DEBUG", "False").lower() in {"1", "true", "yes"}
IS_RENDER = bool(
    os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
    or os.environ.get("RENDER_EXTERNAL_URL", "").strip()
)
ALLOWED_HOSTS = list(
    {
        *csv_env("ALLOWED_HOSTS", "portfolio-show.onrender.com"),
        os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip(),
        "localhost",
        "127.0.0.1",
        "testserver",
    }
)
SITE_ID = int(os.environ.get("SITE_ID", "1") or "1")
CSRF_TRUSTED_ORIGINS = csv_env("CSRF_TRUSTED_ORIGINS")
render_external_url = os.environ.get("RENDER_EXTERNAL_URL", "").strip()
if render_external_url:
    CSRF_TRUSTED_ORIGINS = list({*CSRF_TRUSTED_ORIGINS, render_external_url})

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sitemaps",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "portfolio.apps.PortfolioConfig",
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

CLOUDINARY_STORAGE = {
    "SECURE": True,
}
cloudinary_cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip()
cloudinary_api_key = os.environ.get("CLOUDINARY_API_KEY", "").strip()
cloudinary_api_secret = os.environ.get("CLOUDINARY_API_SECRET", "").strip()
if cloudinary_cloud_name and cloudinary_api_key and cloudinary_api_secret:
    CLOUDINARY_STORAGE.update(
        {
            "CLOUD_NAME": cloudinary_cloud_name,
            "API_KEY": cloudinary_api_key,
            "API_SECRET": cloudinary_api_secret,
        }
    )

CLOUDINARY_MEDIA_ENABLED = bool(
    os.environ.get("CLOUDINARY_URL", "").strip()
    or all(CLOUDINARY_STORAGE.get(key) for key in ("CLOUD_NAME", "API_KEY", "API_SECRET"))
)

if CLOUDINARY_MEDIA_ENABLED:
    INSTALLED_APPS.extend(
        [
            "cloudinary_storage",
            "cloudinary",
        ]
    )

MIDDLEWARE = [
    # CorsMiddleware must be before SecurityMiddleware and any middleware
    # that generates responses such as CommonMiddleware.
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ---------------------------------------------------------------------------
# Database — Neon PostgreSQL (via DATABASE_URL) or SQLite fallback
# ---------------------------------------------------------------------------
# For Neon, use a connection string like:
#   postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/dbname?sslmode=require
# Neon requires SSL — psycopg2-binary supports this via the ?sslmode=require
# query parameter in the connection string.
#
# dj_database_url automatically parses the DATABASE_URL env var.
# The `conn_max_age` setting enables persistent connections (recommended for Neon
# serverless because it reduces cold-start overhead).
# ---------------------------------------------------------------------------
_db_default = "sqlite:///db.sqlite3"
_database_url = os.environ.get("DATABASE_URL", "").strip() or _db_default

# Neon-specific: ensure SSL is required when using Neon's hostname
_neon_host = ".neon.tech"
if _neon_host in _database_url and "sslmode" not in _database_url:
    _database_url = _database_url.rstrip("/") + ("&" if "?" in _database_url else "?") + "sslmode=require"

DATABASES = {
    "default": dj_database_url.parse(
        _database_url,
        conn_max_age=int(os.environ.get("DB_CONN_MAX_AGE", "60")),
        conn_health_checks=True,
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Addis_Ababa"
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STATICFILES_BACKEND = (
    "django.contrib.staticfiles.storage.StaticFilesStorage"
    if DEBUG or "test" in sys.argv
    else "whitenoise.storage.CompressedManifestStaticFilesStorage"
)
STORAGES = {
    "default": {
        "BACKEND": (
            "cloudinary_storage.storage.MediaCloudinaryStorage"
            if CLOUDINARY_MEDIA_ENABLED
            else "django.core.files.storage.FileSystemStorage"
        ),
    },
    "staticfiles": {
        "BACKEND": STATICFILES_BACKEND,
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/"

# ---------------------------------------------------------------------------
# CORS — Cross-Origin Resource Sharing
# ---------------------------------------------------------------------------
# Allow the separately deployed frontend to make credentialed requests.
# Set CORS_ORIGINS in your environment as a comma-separated list of allowed
# origins, e.g.:
#   CORS_ORIGINS=https://portfolio-show.onrender.com,http://localhost:5173
#
# Never use CORS_ALLOW_ALL_ORIGINS=True when credentials are involved.
# ---------------------------------------------------------------------------
_cors_origins_raw = csv_env("CORS_ORIGINS")

# Always allow localhost for development
CORS_ALLOWED_ORIGINS = list(
    {
        *_cors_origins_raw,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8080",
    }
    - {""}  # remove empty strings
)

# Allow credentials (cookies) in cross-origin requests — required for
# Django session authentication to work from a separate frontend origin.
CORS_ALLOW_CREDENTIALS = True

# Allow the CSRF cookie to be read by the frontend's JS
CORS_EXPOSE_HEADERS = ["Content-Type", "X-CSRFToken"]

# ---------------------------------------------------------------------------
# Session & CSRF cookies — cross-origin configuration
# ---------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # JS needs to read this to send in X-CSRFToken header

# When the frontend and backend are on different origins (different domains),
# cookies must use SameSite=None + Secure=True to be sent cross-origin.
# This is automatically applied in production (IS_RENDER=True) or when
# FORCE_CROSS_ORIGIN_COOKIES=true is set.
_force_cross_origin = os.environ.get("FORCE_CROSS_ORIGIN_COOKIES", "").lower() in {"1", "true", "yes"}
_use_cross_origin_cookies = IS_RENDER or _force_cross_origin

if _use_cross_origin_cookies:
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
else:
    # Development default — works for same-origin or localhost
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SECURE_SSL_REDIRECT = IS_RENDER and "test" not in sys.argv

SECURE_VIDEO_STREAM_TTL_SECONDS = int(os.environ.get("SECURE_VIDEO_STREAM_TTL_SECONDS", "300"))
SECURE_VIDEO_DOWNLOAD_TTL_SECONDS = int(os.environ.get("SECURE_VIDEO_DOWNLOAD_TTL_SECONDS", "600"))
SECURE_VIDEO_USE_CLOUDINARY_TOKENS = (
    os.environ.get("SECURE_VIDEO_USE_CLOUDINARY_TOKENS", "true").lower() in {"1", "true", "yes"}
)
CLOUDINARY_AUTH_TOKEN_KEY = os.environ.get("CLOUDINARY_AUTH_TOKEN_KEY", "").strip()
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "no-reply@portfolio-show.local")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_BASE = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org").rstrip("/")
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
GEMINI_API_TIMEOUT_SECONDS = int(os.environ.get("GEMINI_API_TIMEOUT_SECONDS", "20"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
GROQ_API_TIMEOUT_SECONDS = int(os.environ.get("GROQ_API_TIMEOUT_SECONDS", "20"))
GOOGLE_OAUTH_CLIENT_ID_ENV_NAMES = (
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_OAUTH2_CLIENT_ID",
    "SOCIAL_AUTH_GOOGLE_CLIENT_ID",
    "SOCIALACCOUNT_GOOGLE_CLIENT_ID",
)
GOOGLE_OAUTH_CLIENT_SECRET_ENV_NAMES = (
    "GOOGLE_OAUTH_CLIENT_SECRET",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH2_CLIENT_SECRET",
    "SOCIAL_AUTH_GOOGLE_CLIENT_SECRET",
    "SOCIALACCOUNT_GOOGLE_CLIENT_SECRET",
)
GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_ID_VALUES, GOOGLE_OAUTH_CLIENT_ID_ERROR = resolve_env_aliases(
    *GOOGLE_OAUTH_CLIENT_ID_ENV_NAMES
)
GOOGLE_OAUTH_CLIENT_SECRET, GOOGLE_OAUTH_CLIENT_SECRET_VALUES, GOOGLE_OAUTH_CLIENT_SECRET_ERROR = resolve_env_aliases(
    *GOOGLE_OAUTH_CLIENT_SECRET_ENV_NAMES
)
GOOGLE_OAUTH_CONFIG_ERROR = " ".join(
    part
    for part in [
        GOOGLE_OAUTH_CLIENT_ID_ERROR,
        GOOGLE_OAUTH_CLIENT_SECRET_ERROR,
        (
            "Both a Google OAuth client ID and client secret must be set."
            if (GOOGLE_OAUTH_CLIENT_ID and not GOOGLE_OAUTH_CLIENT_SECRET)
            or (GOOGLE_OAUTH_CLIENT_SECRET and not GOOGLE_OAUTH_CLIENT_ID)
            else ""
        ),
    ]
    if part
).strip()

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),
    "DEFAULT_THROTTLE_CLASSES": (),
    "DEFAULT_THROTTLE_RATES": {
        "secure_video_stream": "120/hour",
        "secure_video_like": "20/hour",
        "secure_video_rating": "20/hour",
        "secure_video_upload": "20/hour",
        "secure_video_download_request": "60/hour",
        "secure_video_download_link": "30/hour",
        "secure_owner_review": "60/hour",
        "secure_owner_notifications": "120/hour",
    },
}
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth core settings
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = 'optional'
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {
            "prompt": "select_account",
        },
    }
}
if GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET and not GOOGLE_OAUTH_CONFIG_ERROR:
    SOCIALACCOUNT_PROVIDERS["google"]["APP"] = {
        "client_id": GOOGLE_OAUTH_CLIENT_ID,
        "secret": GOOGLE_OAUTH_CLIENT_SECRET,
        "key": "",
    }
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# ---------------------------------------------------------------------------
# Frontend shell — legacy support
# ---------------------------------------------------------------------------
# The index.html used to live at the project root. After separation, the
# frontend is deployed independently. The FRONTEND_SOURCE path is kept here
# for backward compatibility (e.g. the about page template) but the
# frontend_shell view is no longer the primary way the frontend is served.
#
# If FRONTEND_SOURCE_PATH env var is set, use it; otherwise fall back to the
# project root index.html if it exists (for local dev monorepo runs).
# ---------------------------------------------------------------------------
_frontend_source_env = os.environ.get("FRONTEND_SOURCE_PATH", "").strip()
if _frontend_source_env:
    FRONTEND_SOURCE_PATH = Path(_frontend_source_env)
else:
    # Try backend/../index.html (monorepo root) then backend/../frontend/index.html
    _candidates = [
        BASE_DIR.parent / "index.html",
        BASE_DIR.parent / "frontend" / "index.html",
        BASE_DIR / "index.html",
    ]
    FRONTEND_SOURCE_PATH = next((p for p in _candidates if p.exists()), BASE_DIR.parent / "frontend" / "index.html")

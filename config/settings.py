"""Django settings (SPEC §5, §6).

Every value comes from .env or the environment (read by judge.env, shared with the judge);
there are no defaults here: .env.example is the one place where values live.
"""

from datetime import timedelta
from pathlib import Path

from config.env import Env
from judge.env import read_env
from judge.packaging.zip_validator import ZipLimits

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env(read_env())
env.require(
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DATABASE_URL",
    "TIME_ZONE",
    "MEDIA_ROOT",
    "SUBMISSION_COOLDOWN_S",
    "SUBMISSION_MAX_ACTIVE_PER_STUDENT",
    "SUBMISSION_MAX_ZIP_MB",
    "SUBMISSION_MAX_UNPACKED_MB",
    "SUBMISSION_MAX_FILES",
    "TASK_MAX_ZIP_MB",
    "TASK_MAX_UNPACKED_MB",
    "TASK_MAX_FILES",
)

SECRET_KEY = env.text("DJANGO_SECRET_KEY")
DEBUG = env.flag("DJANGO_DEBUG")
ALLOWED_HOSTS = env.comma_list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "django_tailwind_cli",
    "axes",
    "apps.accounts",
    "apps.tasks",
    "apps.submissions",
    "apps.system",
    "apps.ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a signed-in user unless its view says otherwise (@login_not_required).
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "apps.accounts.middleware.PasswordChangeRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

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
                "apps.accounts.navigation.navigation",
            ],
        },
    },
]

DATABASES = {"default": env.database("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",  # refuses locked-out logins first
    "django.contrib.auth.backends.ModelBackend",
]
# Signed-out visitors land on the page with the two doors (students, staff).
LOGIN_URL = "accounts:home"
LOGIN_REDIRECT_URL = "accounts:home"
LOGOUT_REDIRECT_URL = "accounts:home"
# A session lasts a day at most: classroom computers are shared.
SESSION_COOKIE_AGE = 24 * 60 * 60

# Login lockout (django-axes, SPEC §5). A whole class shares one IP behind the centre's NAT,
# so the lock is per login and IP: a mistyping student never locks out the others.
AXES_FAILURE_LIMIT = 10
AXES_COOLOFF_TIME = timedelta(minutes=15)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_CLIENT_IP_CALLABLE = "apps.accounts.client_ip.client_ip"
AXES_LOCKOUT_TEMPLATE = "accounts/locked.html"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = env.text("TIME_ZONE")
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # Hashed, compressed names in production (served by WhiteNoise, cached for a year);
    # plain names while developing, so nothing needs collectstatic.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}

# Tailwind CSS v4 standalone CLI (no Node): assets/source.css -> static/css/app.css.
# The pinned binary is downloaded once into .django_tailwind_cli/.
TAILWIND_CLI_VERSION = "4.3.3"
TAILWIND_CLI_SRC_CSS = "assets/source.css"
TAILWIND_CLI_DIST_CSS = "css/app.css"
# Uploads are served only by views that check permissions (SPEC §5), so no MEDIA_URL.
# A relative path is under the repository; production uses an absolute one.
MEDIA_ROOT = BASE_DIR / env.text("MEDIA_ROOT")

# HTTPS ends at Caddy, which sets X-Forwarded-Proto; web is reachable only through it.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 0 if DEBUG else 365 * 24 * 60 * 60
SILENCED_SYSTEM_CHECKS = [
    # HSTS covers this host only: other subdomains of the centre's domain may lack HTTPS,
    # and the preload list is a promise that is hard to take back.
    "security.W005",
    "security.W021",
]

# Uploads (SPEC §6). The site checks zips with the same limits as the worker.
_MB = 1024 * 1024
SUBMISSION_ZIP_LIMITS = ZipLimits(
    max_zip_bytes=env.positive_int("SUBMISSION_MAX_ZIP_MB") * _MB,
    max_unpacked_bytes=env.positive_int("SUBMISSION_MAX_UNPACKED_MB") * _MB,
    max_files=env.positive_int("SUBMISSION_MAX_FILES"),
)
TASK_ZIP_LIMITS = ZipLimits(
    max_zip_bytes=env.positive_int("TASK_MAX_ZIP_MB") * _MB,
    max_unpacked_bytes=env.positive_int("TASK_MAX_UNPACKED_MB") * _MB,
    max_files=env.positive_int("TASK_MAX_FILES"),
)
SUBMISSION_COOLDOWN_S = env.positive_int("SUBMISSION_COOLDOWN_S")
SUBMISSION_MAX_ACTIVE_PER_STUDENT = env.positive_int("SUBMISSION_MAX_ACTIVE_PER_STUDENT")
# Django refuses bigger request bodies before any view runs; packages are the biggest.
DATA_UPLOAD_MAX_MEMORY_SIZE = TASK_ZIP_LIMITS.max_zip_bytes + _MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * _MB  # larger uploads are spooled to a temporary file

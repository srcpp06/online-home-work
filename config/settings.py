"""Django settings (SPEC §5, §6).

Every value comes from .env or the environment (read by judge.env, shared with the judge);
there are no defaults here: .env.example is the one place where values live.
"""

from pathlib import Path

from config.env import Env
from judge.env import read_env

BASE_DIR = Path(__file__).resolve().parent.parent

env = Env(read_env())
env.require(
    "DJANGO_SECRET_KEY",
    "DJANGO_DEBUG",
    "DJANGO_ALLOWED_HOSTS",
    "DATABASE_URL",
    "TIME_ZONE",
    "MEDIA_ROOT",
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
    "apps.accounts",
    "apps.ui",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
            ],
        },
    },
]

DATABASES = {"default": env.database("DATABASE_URL")}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"
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

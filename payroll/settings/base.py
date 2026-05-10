"""
Shared settings for the payroll project.

Environment-specific overrides live in ``dev.py`` and ``prod.py``. Sensitive or
environment-dependent values are loaded via ``django-environ`` from a ``.env``
file located at the Django project root (next to ``manage.py``).
"""

from pathlib import Path

import environ

# BASE_DIR points at the Django project root (the directory that contains
# manage.py). settings/base.py is three levels deep from that directory:
# payroll/payroll/settings/base.py -> parents: settings -> payroll -> payroll.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)

# Read .env if present. In production the .env lives on the server and is
# placed by the build script before the application starts.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="django-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Local apps
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "employees.apps.EmployeesConfig",
    "scheduling.apps.SchedulingConfig",
    "attendance.apps.AttendanceConfig",
    "payroll_close.apps.PayrollCloseConfig",
]

# Custom user model — must be set before any migration that references auth.
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:home"
LOGOUT_REDIRECT_URL = "accounts:login"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "payroll.urls"

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

WSGI_APPLICATION = "payroll.wsgi.application"

# Database configuration is left to dev.py / prod.py since the engines differ.

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# Static files. STATICFILES_DIRS holds source assets edited in development;
# STATIC_ROOT is populated by ``collectstatic`` in production.
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR.parent / "staticfiles"

# Media files are stored outside the codebase per rules.md §2 / §12.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR.parent / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

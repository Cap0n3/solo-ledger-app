"""Settings shared by every environment.

Environment-specific values (DEBUG, SECRET_KEY, allowed hosts, strict database
credentials) live in `development.py`, `production.py` and `test.py`.
"""

import os
from pathlib import Path

import django_stubs_ext
from django.contrib.messages import constants as message_constants

# Makes Django's generic classes (ModelAdmin, QuerySet, ...) subscriptable at
# runtime so annotations can match the django-stubs types.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parents[3]
CORE_DIR = BASE_DIR / "core"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core.apps.accounts",
    "core.apps.students",
    "core.apps.accounting",
    "core.apps.bank_imports",
    "core.apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [CORE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.apps.accounts.context_processors.current_profession",
            ],
        },
    },
]

WSGI_APPLICATION = "core.config.wsgi.application"

# Development defaults match .env.example; production.py reads them strictly.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "sololedger"),
        "USER": os.environ.get("POSTGRES_USER", "sololedger"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "sololedger"),
        "HOST": os.environ.get("POSTGRES_HOST", "db"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "reports:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Swiss French: Django falls back to the "fr" catalog and uses fr_CH formats.
LANGUAGE_CODE = "fr-ch"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [CORE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# User uploads (avatars). Django serves them in development only (see
# config/urls.py); production serving belongs to the production milestone.
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Bootstrap alert classes for the messages framework.
MESSAGE_TAGS = {
    message_constants.DEBUG: "secondary",
    message_constants.ERROR: "danger",
}

# Guards `manage.py seed`: only environments that opt in may receive fake data.
SEED_ALLOWED = False

"""Development settings for the Docker Compose stack."""

import os

from .base import *  # noqa: F403

DEBUG = True

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-secret-key")

ALLOWED_HOSTS = ["*"]

SEED_ALLOWED = True

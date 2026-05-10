"""
Development settings. Defaults to SQLite and DEBUG=True.
"""

from .base import *  # noqa: F401,F403
from .base import BASE_DIR, env

DEBUG = env("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["127.0.0.1", "localhost"])

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

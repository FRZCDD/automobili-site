from decouple import Csv, config

from .base import *  # noqa: F403
from .checks import require_secure_secret

DEBUG = False

SECRET_KEY = config("SECRET_KEY")
require_secure_secret("SECRET_KEY", SECRET_KEY, min_len=50)

ALLOWED_HOSTS: list[str] = config("ALLOWED_HOSTS", cast=Csv())
CSRF_TRUSTED_ORIGINS: list[str] = config("CSRF_TRUSTED_ORIGINS", cast=Csv())

# Set when a reverse proxy (nginx, a platform load balancer) terminates TLS in front
# of this app — same convention as automobili-zaluppini.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Hashed filenames + manifest: the browser caches built assets (Tailwind CSS)
# indefinitely, a new deploy is picked up under a new name. The manifest is built by
# the Dockerfile's asset stage, not at container start — this site has no
# `collectstatic` step to run since STATICFILES_DIRS already holds the built CSS.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

USE_HTTPS = config("USE_HTTPS", default=True, cast=bool)
if USE_HTTPS:
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
